import json
from unittest.mock import patch
from django.test import TestCase, Client
from .models import SavedRecipe
from .recipe_format import encode, decode
from .provider import FIXTURES
from .editor import PENDING, UNDO

class EditorTests(TestCase):
    def setUp(self):
        self.original=encode(FIXTURES['kk'])
        self.item=SavedRecipe.objects.create(products='Жұмыртқа, сүт',recipe=self.original,language='kk')
        self.other=SavedRecipe.objects.create(products='Күріш',recipe=self.original,language='kk')
        self.url=f'/edit/{self.item.pk}/'
    def request_proposal(self,**extra):
        return self.client.post(self.url,{'action':'propose','instruction':'Табада дайындауға бейімде',**extra})
    def token(self): return self.client.session[PENDING]['token']
    def stored(self): self.item.refresh_from_db();return self.item.recipe
    def accept(self): return self.client.post(self.url,{'action':'accept','token':self.token()})
    def test_proposal_and_get_never_write_before_accept(self):
        self.assertEqual(self.request_proposal().status_code,302)
        self.assertEqual(self.stored(),self.original)
        self.assertContains(self.client.get(self.url),'Ұсыныс әлі сақталған жоқ')
        self.assertEqual(self.stored(),self.original)
    def test_reject_keeps_exact_original_and_other_recipe(self):
        self.request_proposal();self.client.post(self.url,{'action':'reject','token':self.token()})
        self.assertEqual(self.stored(),self.original);self.assertNotIn(PENDING,self.client.session)
        self.other.refresh_from_db();self.assertEqual(self.other.recipe,self.original)
    def test_accept_ignores_browser_recipe_and_duplicate_accept_is_conflict(self):
        self.request_proposal();token=self.token()
        self.client.post(self.url,{'action':'accept','token':token,'recipe':'FORGED'})
        self.assertNotEqual(self.stored(),self.original);self.assertIsNotNone(decode(self.stored()))
        self.assertEqual(self.client.post(self.url,{'action':'accept','token':token}).status_code,409)
    def test_undo_restores_exact_text_once_and_keeps_other_recipe(self):
        self.request_proposal();self.accept();undo=self.client.session[UNDO]['token']
        self.assertEqual(self.client.post(self.url,{'action':'undo','token':undo}).status_code,302)
        self.assertEqual(self.stored(),self.original)
        self.assertEqual(self.client.post(self.url,{'action':'undo','token':undo}).status_code,409)
        self.other.refresh_from_db();self.assertEqual(self.other.recipe,self.original)
    def test_bad_responses_provider_exception_and_untrusted_html(self):
        bad=['','not json','{}','{"title":"a","title":"b","ingredients":["x"],"steps":["x"]}',json.dumps({'title':'x','ingredients':['x'],'steps':[]}),json.dumps({'title':'x','ingredients':['x'],'steps':['x'],'extra':'x'}),'x'*30001]
        for raw in bad:
            with self.subTest(raw=raw[:80]),patch('recipes.editor.propose',return_value=raw):
                self.assertEqual(self.request_proposal().status_code,422)
                self.assertEqual(self.stored(),self.original);self.assertNotIn(PENDING,self.client.session)
        with patch('recipes.editor.propose',side_effect=RuntimeError('SECRET_VALUE')):
            response=self.request_proposal();self.assertNotContains(response,'SECRET_VALUE',status_code=422)
        raw=json.dumps({'title':'<script>alert(1)</script>','ingredients':['x'],'steps':['x']})
        with patch('recipes.editor.propose',return_value=raw):self.request_proposal()
        self.assertContains(self.client.get(self.url),'&lt;script&gt;')
        self.assertNotContains(self.client.get(self.url),'<script>alert(1)</script>')
    def test_empty_and_long_instruction_no_provider_call(self):
        with patch('recipes.editor.propose') as provider:
            for instruction in ('','ab','x'*301):
                self.assertEqual(self.request_proposal(instruction=instruction).status_code,400)
            provider.assert_not_called()
        self.assertEqual(self.stored(),self.original)
    def test_only_one_pending_and_session_isolation(self):
        self.request_proposal();token=self.token()
        self.assertEqual(self.request_proposal().status_code,409)
        self.assertEqual(self.client.post(f'/edit/{self.other.pk}/',{'action':'accept','token':token}).status_code,409)
        self.assertEqual(Client().post(self.url,{'action':'accept','token':token}).status_code,409)
        self.assertEqual(self.stored(),self.original)
    def test_expired_proposal_cannot_accept(self):
        self.request_proposal();token=self.token();s=self.client.session;p=s[PENDING];p['expires']=0;s[PENDING]=p;s.save()
        self.assertEqual(self.client.post(self.url,{'action':'accept','token':token}).status_code,409)
        self.assertEqual(self.stored(),self.original)
    def test_stale_accept_and_undo_cannot_overwrite_concurrent_change(self):
        self.request_proposal();SavedRecipe.objects.filter(pk=self.item.pk).update(recipe='external')
        self.assertEqual(self.accept().status_code,409);self.assertEqual(self.stored(),'external')
        SavedRecipe.objects.filter(pk=self.item.pk).update(recipe=self.original)
        self.request_proposal();self.accept();undo=self.client.session[UNDO]['token']
        SavedRecipe.objects.filter(pk=self.item.pk).update(recipe='new external')
        self.assertEqual(self.client.post(self.url,{'action':'undo','token':undo}).status_code,409)
        self.assertEqual(self.stored(),'new external')
    def test_csrf_post_only_actions_and_no_recipe_404(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url,{'action':'propose'}).status_code,403)
        with patch('recipes.editor.propose') as provider:
            self.client.get(self.url+'?action=accept');provider.assert_not_called()
        self.assertEqual(self.client.get('/edit/999999/').status_code,404)
        self.assertEqual(self.stored(),self.original)
    def test_legacy_is_unchanged_and_blocked_for_edit(self):
        SavedRecipe.objects.filter(pk=self.item.pk).update(recipe='Бұрынғы мәтін. Бөлме.')
        with patch('recipes.editor.propose') as provider:
            self.assertEqual(self.request_proposal().status_code,422);provider.assert_not_called()
        self.assertEqual(self.stored(),'Бұрынғы мәтін. Бөлме.')
    def test_rollback_survives_new_browser_client_with_same_session_and_cooking_works(self):
        self.request_proposal();self.accept();undo=self.client.session[UNDO]['token']
        new=Client();new.cookies=self.client.cookies
        self.assertEqual(new.get(f'/cook/{self.item.pk}/').status_code,200)
        self.assertEqual(new.post(self.url,{'action':'undo','token':undo}).status_code,302)
        self.assertEqual(self.stored(),self.original)
    def test_timeout_leaves_no_candidate_and_exact_original(self):
        with patch('recipes.editor.propose',side_effect=TimeoutError('provider timeout')):
            self.assertEqual(self.request_proposal().status_code,422)
        self.assertEqual(self.stored(),self.original);self.assertNotIn(PENDING,self.client.session)
    def test_failed_snapshot_save_rolls_back_recipe_update(self):
        self.request_proposal()
        with patch('django.contrib.sessions.backends.db.SessionStore.save',side_effect=RuntimeError('snapshot failure')):
            with self.assertRaises(RuntimeError):self.accept()
        self.assertEqual(self.stored(),self.original)
    def test_only_latest_accept_snapshot_survives_and_reject_keeps_undo(self):
        self.request_proposal();self.accept();first=self.stored();undo=dict(self.client.session[UNDO])
        candidate={**decode(first),'title':'Екінші өзгеріс'}
        with patch('recipes.editor.propose',return_value=json.dumps(candidate)):
            self.request_proposal();self.client.post(self.url,{'action':'reject','token':self.token()})
            self.assertEqual(dict(self.client.session[UNDO]),undo)
            self.request_proposal();self.accept()
        self.assertEqual(self.client.session[UNDO]['before'],first)
        self.client.post(self.url,{'action':'undo','token':self.client.session[UNDO]['token']})
        self.assertEqual(self.stored(),first)

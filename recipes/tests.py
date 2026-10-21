import json, uuid
from unittest.mock import patch
from django.test import TestCase, Client
from .models import SavedRecipe
from .provider import FIXTURES
from .recipe_format import validate, parse_response, encode, decode, as_text, RecipeFormatError, PREFIX


class FormatTests(TestCase):
    def test_roundtrip_and_one_step(self):
        data={"title":"Шаговый рецепт","ingredients":["Яйцо"],"steps":["Смешай и приготовь."]}
        self.assertEqual(decode(encode(data)),data)
        self.assertIn("1. Смешай",as_text(data))
    def test_rejects_wrong_shapes(self):
        for data in (None,[],{},dict(FIXTURES['ru'],steps=[]),dict(FIXTURES['ru'],steps='abc'),dict(FIXTURES['ru'],steps=[1]),dict(FIXTURES['ru'],steps=[' ']),dict(FIXTURES['ru'],steps=['x'*1201]),dict(FIXTURES['ru'],title=''),dict(FIXTURES['ru'],extra=True),dict(FIXTURES['ru'],ingredients=[])):
            with self.subTest(data=data):
                with self.assertRaises(RecipeFormatError):validate(data)
        for raw in ('', 'not JSON','```json\n{}\n```','null','['*2000,'x'*30001,'{"title":"A","title":"B","ingredients":["x"],"steps":["x"]}'):
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(RecipeFormatError):parse_response(raw)
    def test_legacy_not_split(self):
        legacy='1.5 чайной ложки. Dr. Cook. Пример!'
        self.assertIsNone(decode(legacy))
        self.assertIsNone(decode(PREFIX+'not JSON'))
    def test_html_stays_text(self):
        data=dict(FIXTURES['ru'],steps=['<script>alert(1)</script>'])
        self.assertEqual(decode(encode(data))['steps'],data['steps'])


class WorkflowTests(TestCase):
    def setUp(self):
        self.payload={'action':'generate','selected_products':['egg','milk','cheese'],'products':'укроп','minutes':'15'}
    def make_recipe(self):
        with patch('recipes.views.generate',return_value=json.dumps(FIXTURES['ru'])):
            response=self.client.post('/?language=ru',self.payload)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Начать готовку')
        return self.client.session['smartchef_draft']
    def test_generate_session_save_no_duplicates_and_saved_cooking(self):
        old=SavedRecipe.objects.create(token=uuid.uuid4(),products='картофель',recipe='Старый рецепт. Не делить!',language='ru',minutes=30,vegetarian=True)
        draft=self.make_recipe()
        self.assertEqual(draft['products'],'Яйцо, Молоко, Сыр, укроп')
        with patch('recipes.views.generate') as provider:
            self.client.post('/save/');self.client.post('/save/')
            self.assertEqual(SavedRecipe.objects.count(),2)
            self.client.get('/saved/');self.client.get('/cook/draft/')
            new=SavedRecipe.objects.get(token=draft['token'])
            self.assertEqual(self.client.get(f'/cook/{new.id}/').status_code,200)
            provider.assert_not_called()
        old.refresh_from_db();self.assertEqual(old.recipe,'Старый рецепт. Не делить!')
        self.assertEqual(self.client.get(f'/cook/{old.id}/').status_code,422)
        self.assertEqual(self.client.get('/save/').status_code,405)
    def test_bad_response_clears_old_draft_without_fake_recipe(self):
        for raw in ('', '{}','not JSON',json.dumps(dict(FIXTURES['ru'],steps=[]))):
            self.make_recipe()
            with patch('recipes.views.generate',return_value=raw):response=self.client.post('/?language=ru',self.payload)
            self.assertContains(response,'Ответ не подходит')
            self.assertNotIn('smartchef_draft',self.client.session)
            self.assertNotContains(response,'href="/cook/draft/')
            self.assertNotContains(response,'action="/save/"')
    def test_unknown_products_and_invalid_minutes_never_call_provider(self):
        for extra in ({'selected_products':['invented']},{'minutes':'abc'},{'minutes':'999'},{'selected_products':[],'products':''}):
            with patch('recipes.views.generate') as provider:
                self.client.post('/',dict(self.payload,**extra));provider.assert_not_called()
    def test_language_keeps_selection_and_does_not_call_provider(self):
        self.make_recipe()
        with patch('recipes.views.generate') as provider:
            response=self.client.post('/?language=ru',dict(self.payload,action='language'))
            provider.assert_not_called()
        self.assertContains(response,'value="egg" checked')
        self.assertNotIn('smartchef_draft',self.client.session)
    def test_structured_html_is_escaped_and_no_execution(self):
        data=dict(FIXTURES['ru'],title='<img src=x onerror=alert(1)>',steps=['<script>alert(1)</script>'])
        with patch('recipes.views.generate',return_value=json.dumps(data)):response=self.client.post('/?language=ru',self.payload)
        self.assertContains(response,'&lt;script&gt;')
        cook=self.client.get('/cook/draft/?language=ru')
        self.assertNotContains(cook,'<script>alert(1)</script>')
        self.assertContains(cook,'\\u003Cscript\\u003E')
    def test_tampered_draft_and_corrupt_saved_record(self):
        session=self.client.session
        session['smartchef_draft']={'token':'not-uuid','recipe':'x'};session.save()
        self.client.post('/save/');self.assertEqual(SavedRecipe.objects.count(),0)
        self.assertEqual(self.client.get('/cook/draft/').status_code,422)
        corrupt=SavedRecipe.objects.create(products='abc',recipe=PREFIX+'{bad}',language='ru',minutes=30)
        self.assertEqual(self.client.get(f'/cook/{corrupt.id}/').status_code,422)
        self.assertEqual(self.client.get('/cook/999999/').status_code,404)
    def test_existing_legacy_session_still_saves_once(self):
        session=self.client.session;token=str(uuid.uuid4())
        session['smartchef_draft']={'token':token,'products':'яйцо','recipe':'Текстовый старый рецепт.','language':'ru','minutes':15,'vegetarian':False};session.save()
        self.client.post('/save/');self.client.post('/save/')
        self.assertEqual(SavedRecipe.objects.filter(token=token).count(),1)
    def test_exit_can_restore_unsaved_draft_without_provider(self):
        self.make_recipe()
        with patch('recipes.views.generate') as provider:
            response=self.client.get('/?draft=1&language=ru')
            provider.assert_not_called()
        self.assertContains(response,'Начать готовку')
        self.assertContains(response,'action="/save/"')
    def test_completion_returns_to_unsaved_draft_and_saved_collection(self):
        draft=self.make_recipe()
        with patch('recipes.views.generate') as provider:
            response=self.client.get('/cook/draft/?language=ru')
            self.assertContains(response,'id="cook-return" class="button" href="/?draft=1&amp;language=ru"')
            returned=self.client.get(response.context['return_href'])
            self.assertContains(returned,'action="/save/"')
            self.assertEqual(SavedRecipe.objects.count(),0)
            self.assertEqual(self.client.session['smartchef_draft']['token'],draft['token'])
            self.client.post('/save/')
            saved=SavedRecipe.objects.get(token=draft['token'])
            response=self.client.get(f'/cook/{saved.id}/?language=ru')
            self.assertContains(response,'id="cook-return" class="button" href="/saved/?language=ru"')
            provider.assert_not_called()
    def test_csrf_required(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/',self.payload).status_code,403)
        self.assertEqual(client.post('/save/').status_code,403)

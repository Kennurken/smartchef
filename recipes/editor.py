"""Session-scoped proposal + one previous version. Database writes use compare-and-swap."""
import time
import uuid
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render, redirect
from .models import SavedRecipe
from .recipe_format import decode, parse_response, encode
from .editor_provider import propose
from .views import context

PENDING='smartchef_edit_pending'
UNDO='smartchef_edit_undo'
TTL=600

def editor(request,recipe_id):
    if request.method not in ('GET','POST'): return HttpResponseNotAllowed(['GET','POST'])
    # Lab 04–06 is a single-user localhost project, no owner field. For an authenticated
    # student app this lookup MUST retain its existing owner-filtered queryset.
    item=get_object_or_404(SavedRecipe,pk=recipe_id)
    lang=item.language if item.language in ('kk','ru') else 'kk'
    message=''; error=''; status=200
    pending=request.session.get(PENDING)
    if pending and (pending.get('expires',0)<time.time()):
        request.session.pop(PENDING,None); pending=None
    if request.method=='POST':
        action=request.POST.get('action')
        token=request.POST.get('token','')
        if action=='propose':
            if pending:
                error='Алдымен ашық ұсынысты қабылда немесе бас тарт.';status=409
            else:
                instruction=request.POST.get('instruction','').strip()
                original=decode(item.recipe)
                if not original:
                    error='Бұл ескі мәтіндік рецепт. Оны өзгертпейміз; №6 құрылымды рецептін таңда.';status=422
                elif not 3<=len(instruction)<=300:
                    error='Өзгерісті 3–300 таңбамен жаз.';status=400
                else:
                    try:
                        candidate=parse_response(propose(original,instruction,lang,request.POST.get('scenario','valid')))
                        if candidate==original: raise ValueError('no change')
                        request.session[PENDING]={'recipe_id':item.pk,'original':item.recipe,'candidate':encode(candidate),'instruction':instruction,'token':str(uuid.uuid4()),'expires':time.time()+TTL}
                        return redirect('edit_recipe',recipe_id=item.pk)
                    except Exception:
                        error='Ұсыныс алынбады немесе жауап пішімі қате. Бастапқы рецепт сақталды.';status=422
        elif action in ('accept','reject'):
            if not pending or pending['recipe_id']!=item.pk or pending['token']!=token:
                error='Ұсыныс ескірді немесе басқа рецептке тиесілі. Бетті жаңарт.';status=409
            elif action=='reject':
                request.session.pop(PENDING,None)
                return redirect('/edit/%s/?state=rejected'%item.pk)
            else:
                with transaction.atomic():
                    changed=SavedRecipe.objects.filter(pk=item.pk,recipe=pending['original']).update(recipe=pending['candidate'])
                    if changed:
                        request.session[UNDO]={'recipe_id':item.pk,'before':pending['original'],'after':pending['candidate'],'token':str(uuid.uuid4())}
                        request.session.pop(PENDING,None)
                        # DB-backed sessions in this demo share the same database transaction.
                        request.session.save()
                        return redirect('/edit/%s/?state=accepted'%item.pk)
                request.session.pop(PENDING,None)
                error='Рецепт басқа бетте өзгерген. Ескі ұсыныс сақталмады.';status=409
        elif action=='undo':
            undo=request.session.get(UNDO)
            if not undo or undo['recipe_id']!=item.pk or undo['token']!=token:
                error='Қалпына келтіру қолжетімсіз немесе ескірген.';status=409
            else:
                with transaction.atomic():
                    changed=SavedRecipe.objects.filter(pk=item.pk,recipe=undo['after']).update(recipe=undo['before'])
                    if changed:
                        request.session.pop(UNDO,None);request.session.pop(PENDING,None)
                        request.session.save()
                        return redirect('/edit/%s/?state=restored'%item.pk)
                error='Рецепт басқа бетте өзгерген. Қалпына келтіру тоқтатылды.';status=409
        else:
            error='Белгісіз әрекет.';status=400
    states={'accepted':'Өзгеріс қабылданды. Алдыңғы нұсқаны бір рет қайтара аласың.', 'rejected':'Ұсыныстан бас тартылды. Бастапқы рецепт өзгерген жоқ.', 'restored':'Алдыңғы нұсқа қалпына келтірілді.'}
    message=states.get(request.GET.get('state'),'') if request.method=='GET' else ''
    item.refresh_from_db()
    pending=request.session.get(PENDING)
    pending=pending if pending and pending['recipe_id']==item.pk else None
    undo=request.session.get(UNDO)
    undo=undo if undo and undo['recipe_id']==item.pk and undo['after']==item.recipe else None
    ctx=context(lang)
    ctx.update(item=item,current=decode(pending['original'] if pending else item.recipe),candidate=decode(pending['candidate']) if pending else None,pending=pending,undo=undo,error=error,message=message,can_edit=decode(item.recipe) is not None)
    return render(request,'recipes/editor.html',ctx,status=status)

import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import SavedRecipe
from .catalog import CATEGORIES, PRODUCTS, build_products
from .provider import generate, is_demo
from .recipe_format import parse_response, encode, decode, as_text, PREFIX
from .labels import LABELS

def context(language):
    return {"language":language,"labels":LABELS[language],"demo":is_demo()}
def index(request):
    language = request.GET.get("language", request.session.get("language", "kk"))
    language = language if language in LABELS else "kk"
    products=""; minutes=30; vegetarian=False; selected=[]; error=""; recipe=""; recipe_title=""; can_cook=False
    if request.method == "POST":
        products=request.POST.get("products", "").strip()
        raw_ids=request.POST.getlist("selected_products")
        selected=list(dict.fromkeys(p for p in raw_ids if p in {x["id"] for x in PRODUCTS}))
        vegetarian=request.POST.get("vegetarian") == "on"
        try: minutes=int(request.POST.get("minutes", "30"))
        except (ValueError,TypeError): minutes=0
        action=request.POST.get("action")
        request.session.pop("smartchef_draft", None)
        if action == "language":
            language="ru" if language == "kk" else "kk"
            if minutes not in (15,30,60):minutes=30
        elif action == "generate":
            try:
                if minutes not in (15,30,60):raise ValueError("minutes")
                selected,combined=build_products(raw_ids,products,language)
                raw=generate(combined,minutes,vegetarian,language,structured=True,scenario=request.POST.get("scenario","valid"))
                data=parse_response(raw)
                stored=encode(data);recipe=as_text(data);recipe_title=data["title"];can_cook=True
                request.session["smartchef_draft"]={"token":str(uuid.uuid4()),"products":combined,"recipe":stored,"language":language,"minutes":minutes,"vegetarian":vegetarian}
            except Exception:
                # No raw provider errors, credentials, traceback or fake replacement recipe in the UI.
                error=LABELS[language]["error"]
    if request.method == "GET" and request.GET.get("draft") == "1":
        draft=request.session.get("smartchef_draft")
        if valid_draft(draft):
            data=decode(draft["recipe"])
            recipe=as_text(data) if data else draft["recipe"]
            recipe_title=data["title"] if data else "SmartChef"
            can_cook=data is not None
    request.session["language"]=language
    ctx=context(language)
    ctx.update(products=products,minutes=minutes,vegetarian=vegetarian,selected_products=selected,error=error,recipe=recipe,recipe_title=recipe_title,can_cook=can_cook,can_save=bool(recipe),categories=CATEGORIES,catalog_products=PRODUCTS,times=[15,30,60],catalog_data={"categories":CATEGORIES,"products":PRODUCTS,"language":language})
    return render(request,"recipes/index.html",ctx)

def valid_draft(draft):
    if not isinstance(draft,dict):return False
    try:
        uuid.UUID(draft["token"])
        return (isinstance(draft["recipe"],str) and bool(draft["recipe"].strip()) and len(draft["recipe"])<=30000 and isinstance(draft["products"],str) and 3<=len(draft["products"])<=500 and draft["language"] in LABELS and type(draft["minutes"]) is int and draft["minutes"] in (15,30,60) and type(draft["vegetarian"]) is bool)
    except (KeyError,ValueError,TypeError,AttributeError):return False

@require_POST
def save_recipe(request):
    draft=request.session.get("smartchef_draft")
    if not valid_draft(draft):return redirect("index")
    if draft["recipe"].startswith(PREFIX) and decode(draft["recipe"]) is None:return redirect("index")
    SavedRecipe.objects.get_or_create(token=draft["token"],defaults={k:draft[k] for k in ("products","recipe","language","minutes","vegetarian")})
    return redirect("saved_recipes")

def saved_recipes(request):
    language=request.GET.get("language",request.session.get("language","kk"));language=language if language in LABELS else "kk"
    entries=[]
    for item in SavedRecipe.objects.all():
        data=decode(item.recipe);display=as_text(data) if data else item.recipe;title=data["title"] if data else "SmartChef";can_cook=data is not None
        entries.append(dict(id=item.id,products=item.products,display=display,title=title,can_cook=can_cook,created_at=item.created_at,minutes=item.minutes))
    ctx=context(language);ctx["entries"]=entries
    return render(request,"recipes/saved.html",ctx)

def cooking(request, recipe_id=None):
    language=request.GET.get("language",request.session.get("language","kk"));language=language if language in LABELS else "kk"
    if recipe_id is None:
        draft=request.session.get("smartchef_draft")
        stored=draft.get("recipe", "") if valid_draft(draft) else ""
    else:stored=get_object_or_404(SavedRecipe,pk=recipe_id).recipe
    data=decode(stored)
    ctx=context(language);ctx["cooking_data"]=data
    ctx["return_href"]=("/saved/" if recipe_id is not None else "/?draft=1&") + ("?language=" if recipe_id is not None else "language=") + language
    return render(request,"recipes/cooking.html",ctx,status=200 if data else 422)

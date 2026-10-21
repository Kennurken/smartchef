"""Versioned JSON in the existing TextField. No schema migration, no text splitting."""
import json
PREFIX = "SMARTCHEF_JSON_V1\n"
class RecipeFormatError(ValueError): pass
def clean_text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 and c not in "\n\t" for c in value):
        raise RecipeFormatError("invalid text")
    return value.strip()
def validate(data):
    if not isinstance(data,dict) or set(data)!={"title","ingredients","steps"}:raise RecipeFormatError("keys")
    title=clean_text(data["title"],120)
    result={"title":title}
    for key,minimum,maximum,limit in (("ingredients",1,24,200),("steps",1,12,1200)):
        values=data[key]
        if not isinstance(values,list) or not minimum<=len(values)<=maximum:raise RecipeFormatError(key)
        result[key]=[clean_text(value,limit) for value in values]
    return result
def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise RecipeFormatError("duplicate key")
        result[key]=value
    return result
def parse_response(raw):
    if not isinstance(raw,str) or len(raw)>30000:raise RecipeFormatError("size")
    try:return validate(json.loads(raw,object_pairs_hook=unique_object))
    except (ValueError,TypeError,RecursionError) as e:raise RecipeFormatError("JSON") from e
def encode(data):return PREFIX+json.dumps(validate(data),ensure_ascii=False,separators=(",",":"))
def decode(stored):
    if not isinstance(stored,str) or not stored.startswith(PREFIX):return None
    try:return parse_response(stored[len(PREFIX):])
    except RecipeFormatError:return None
def as_text(data):
    return data["title"]+"\n\n"+", ".join(data["ingredients"])+"\n\n"+"\n".join(f"{i}. {step}" for i,step in enumerate(data["steps"],1))

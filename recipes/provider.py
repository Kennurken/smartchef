import json
from django.conf import settings
from dotenv import dotenv_values

FIXTURES = {
 "kk": {"title":"Көкөніс қосылған омлет", "ingredients":["Жұмыртқа", "Ірімшік", "Сүт", "Аскөк"], "steps":["Қолыңды жу. Жұмыртқаны ыдысқа жарып, сүтпен араластыр.", "Ірімшікті үккіштен өткізіп, аскөкті тура. Қоспаға қос.", "Табаны қыздырып, қоспаны құй. Баяу отта дайын болғанша пісір.", "Плитаны өшір. Омлетті тәрелкеге салып, жылы күйінде ұсын."]},
 "ru": {"title":"Омлет с зеленью", "ingredients":["Яйцо", "Сыр", "Молоко", "Укроп"], "steps":["Вымой руки. Разбей яйцо в миску и смешай с молоком.", "Натри сыр, нарежь укроп и добавь их в смесь.", "Разогрей сковороду, вылей смесь и готовь на слабом огне до готовности.", "Выключи плиту. Переложи омлет на тарелку и подай тёплым."]}
}
def config():
    return dotenv_values(settings.BASE_DIR / ".env")
def is_demo():
    return config().get("SMARTCHEF_DEMO", "1") == "1"
def generate(products, minutes, vegetarian, language, structured=False, scenario="valid"):
    if is_demo():
        # Explicit deterministic fixture. Never presented as a live Gemini result.
        if scenario == "empty": return ""
        if scenario == "invalid": return '{"title":"Broken","ingredients":[],"steps":"not a list"}'
        if scenario == "error": raise RuntimeError("fixture failure")
        data = FIXTURES[language]
        if structured: return json.dumps(data, ensure_ascii=False)
        return data["title"] + "\n\n" + "\n".join(data["steps"])
    values = config()
    key = (values.get("GEMINI_API_KEY") or "").strip()
    model = (values.get("GEMINI_MODEL") or "").strip()
    if not key or key == "PASTE_YOUR_KEY_HERE" or not model or model == "SET_YOUR_EXISTING_MODEL":
        raise RuntimeError("missing local configuration")
    from google import genai
    prompt = f"Recipe in {language}. Products: {products}. Maximum {minutes} minutes. Vegetarian: {vegetarian}."
    if structured:
        prompt += ' Return only one JSON object with exactly title (nonempty string), ingredients (1–24 nonempty strings) and steps (1–12 nonempty ordered instruction strings). No Markdown, no HTML, no extra keys. Every step is a complete instruction, not an individual sentence fragment.'
    client = genai.Client(api_key=key)
    # Keep the known project API adapter; this preparation does not verify live availability.
    interaction = client.interactions.create(model=model, input=prompt)
    return interaction.output_text

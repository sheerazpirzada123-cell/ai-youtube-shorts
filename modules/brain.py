from google import genai
from google.genai import errors as genai_errors

import json
import random
import time
import uuid
from datetime import datetime


FACT_TOPICS = [

    "Wahiyat aur Ajeeb Facts",

    "Insaan ke Jism ke Mind-Blowing Sach",

    "Janwaro ki Shocking Duniya",

    "Antariksh ke Khaufnak Facts",

    "Psychology ke Magical Facts",

    "History ke Chaunka Dene Wale Raaz",

    "Crime aur Mystery Facts",

    "Food aur Khane-Peene ke Ajeeb Sach",

    "Technology ke Hairat-Angez Facts",

    "Duniya ke Ajeeb Kanoon aur Riwaj",

    "Paisa aur Ameer Logo ke Facts",

    "Sapno aur Neend ke Raaz",

    "Prachin Sabhyata aur Khazano ke Raaz",

    "Samandar aur Uski Gehraiyon ke Raaz",

    "Dimaag ko Hila Dene Wale Science Facts",

    "Bollywood aur Entertainment ke Anjaane Facts",

    "Sports ki Duniya ke Shocking Facts",

    "Haiwano aur Insaano ke Ajeeb Rishtey",

    "Duniya ki Sabse Ajeeb Jagahen",

    "Nature ke Impossible Lagnewale Facts",

    "Human Psychology ke Hidden Facts",

    "Future aur Science ke Hairat Angeiz Facts"
]


ANGLE_POOL = [

    "kam mashhoor aur underrated facts chuno",

    "counter-intuitive facts chuno jo pehli baar sunne par unbelievable lagen",

    "rare scientific discoveries se related facts chuno",

    "history ke hidden ya unusual facts chuno",

    "strange numbers aur statistics wale facts chuno",

    "real life mysteries aur unexplained phenomena ke facts chuno",

    "animals ke unusual survival abilities wale facts chuno",

    "human body ke lesser-known facts chuno",

    "space ke strange aur mind-blowing facts chuno",

    "nature ke impossible lagne wale facts chuno",

    "aise facts chuno jo aam YouTube facts channels par baar baar repeat nahi hote"
]


HOOK_STYLES = [

    "Kya aapko pata hai",

    "Ye fact sunke aap hairaan reh jaoge",

    "Duniya ka ye sach shayad aapne pehle kabhi nahi suna hoga",

    "Ruko, ye fact aapki soch badal sakta hai",

    "Aapko lagta hai aap duniya ko jaante hain, lekin ye dekho",

    "Ye sach itna ajeeb hai ke pehli baar mein yakeen nahi hoga",

    "Aaj ka ye fact aapko zaroor surprise karega"
]


CTA_STYLES = [

    "Aise hi hairaan kar dene wale facts ke liye follow karo",

    "Roz naye shocking facts ke liye channel ko follow karo",

    "Agar ye fact naya tha to aur facts ke liye follow karo",

    "Aise mind-blowing facts ke liye subscribe zaroor karo"
]


def generate_fact_script(api_key):

    """
    Har workflow run par completely naya
    generation seed use hota hai.
    """

    client = genai.Client(
        api_key=api_key
    )


    # ------------------------------------------
    # UNIQUE RUN ID
    # ------------------------------------------

    run_id = uuid.uuid4().hex


    current_time = (
        datetime.utcnow()
        .strftime("%Y-%m-%d %H:%M:%S UTC")
    )


    # Random seed Gemini ko har request
    # ko different creative direction dene mein help karta hai.

    random_seed = random.randint(
        100000,
        999999999
    )


    selected_topic = random.choice(
        FACT_TOPICS
    )


    selected_angle = random.choice(
        ANGLE_POOL
    )


    selected_hook = random.choice(
        HOOK_STYLES
    )


    selected_cta = random.choice(
        CTA_STYLES
    )


    print(
        "Generating unique script..."
    )

    print(
        f"Run ID: {run_id}"
    )

    print(
        f"Topic: {selected_topic}"
    )

    print(
        f"Seed: {random_seed}"
    )


    prompt = f"""

You are an expert viral YouTube Shorts scriptwriter.

Your task is to generate ONE completely fresh and unique Hindi facts
YouTube Short.

IMPORTANT UNIQUE GENERATION DATA:

RUN ID:
{run_id}

RANDOM CREATIVE SEED:
{random_seed}

GENERATION TIME:
{current_time}

TOPIC:
{selected_topic}

CREATIVE ANGLE:
{selected_angle}

PREFERRED HOOK STYLE:
{selected_hook}

PREFERRED CTA STYLE:
{selected_cta}


CRITICAL UNIQUENESS REQUIREMENT:

Every workflow run must create a DIFFERENT script.

Do NOT reuse common YouTube facts such as:

- humans use only ten percent brain
- honey never expires
- octopus has three hearts
- banana is radioactive
- sharks are older than trees

Avoid overused viral facts unless absolutely necessary.

Choose less common, interesting, surprising and credible facts.

The exact narration, fact selection, hook,
title, description and scene structure must be
fresh and different for this generation.

Do not create a generic repeated facts script.

This video should feel like a new professional
Facts Mine style video every time.


VIDEO FORMAT:

Create approximately thirty to forty five seconds
of narration.

Divide the video into nine to fourteen short scenes -
more, shorter scenes with fast cuts, not fewer long ones.

Each scene should naturally connect with the next.

The video must feel:

- fast paced
- energetic
- surprising
- natural
- human written
- highly engaging


LANGUAGE:

Use natural spoken Hindi written ONLY in Devanagari.

The narration should be understandable for both:

- Indian audience
- Pakistani / Hindi-Urdu understanding audience


Do not use English words in narration.

Do not use Roman Urdu in narration.

Do not use English letters.

Do not use digits.

All numbers must be written in Hindi words.

Examples:

one hundred → सौ

two thousand twenty six →
दो हजार छब्बीस

fifty percent →
पचास प्रतिशत


TTS PRONUNCIATION RULES:

Narration must be easy for a Hindi neural voice
to pronounce naturally.

Avoid:

- complicated English terminology
- abbreviations
- symbols
- digits
- slash characters
- percentage symbols

If a technical term is required,
write its Hindi pronunciation in Devanagari.


SCENE RULES:

Scene one must have a very strong curiosity hook.

Each scene's narration must contain EXACTLY ONE spoken
sentence - never combine two or more sentences into a
single scene. If a fact needs multiple sentences, split
it across multiple scenes so every sentence gets its own
scene and its own visual clip. This is critical: more
short scenes with fast-changing visuals, one sentence
each, feels far more energetic than fewer long scenes.

Do not overload scenes with too much information.

Each narration should sound natural when spoken
by a human, and should be easy to clearly understand
when spoken quickly and energetically (short, simple
sentence structure - avoid long or complicated sentences
that become hard to follow at a fast pace).

Final scene should contain the CTA.


VISUAL KEYWORDS:

Every scene must contain:

"visual_keyword"

Visual keywords must:

- be in English
- contain two to five words
- directly match the scene
- work well for stock video search
- be generic enough for Pexels/Pixabay

Do not use famous people's names.

Do not use brand names.


YOUTUBE TITLE RULES:

Create a curiosity based title.

Use one suitable emoji.

Maximum approximately seventy characters.

Do not include hashtags in title.

The title must be different from generic titles
such as "Amazing Facts You Didn't Know".


DESCRIPTION:

Write two to three short lines.

Make it engaging and curiosity driven.

After that add ten to fifteen relevant hashtags.


TAGS:

Return fifteen to twenty individual SEO tags.

Mix:

- facts
- hindi facts
- amazing facts
- viral facts
- shorts
- youtube shorts

with topic specific tags.


FACT ACCURACY:

Facts must be credible.

Do not invent facts.

Do not exaggerate scientific claims.

If a fact is uncertain,
do not use it.


OUTPUT FORMAT:

Return ONLY valid JSON.

Do not use markdown.

Use exactly this structure:

{{
    "title": "Title here",
    "description": "Description here",
    "tags": [
        "tag one",
        "tag two"
    ],
    "scenes": [
        {{
            "narration": "Scene narration here",
            "visual_keyword": "english stock video search"
        }}
    ]
}}

"""


    response = _generate_with_retry(
        client,
        prompt
    )


    clean_text = (
        response.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


    try:

        script = json.loads(
            clean_text
        )


    except json.JSONDecodeError as e:

        print(
            "Invalid JSON received from Gemini:"
        )

        print(
            clean_text
        )

        raise ValueError(
            f"Gemini returned invalid JSON: {e}"
        )


    # ------------------------------------------
    # BASIC VALIDATION
    # ------------------------------------------

    if (
        "scenes" not in script
        or not isinstance(
            script["scenes"],
            list
        )
    ):

        raise ValueError(
            "Generated script has no valid scenes."
        )


    if len(script["scenes"]) < 7:

        raise ValueError(
            "Generated script has too few scenes."
        )


    print(
        f"Unique script generated successfully."
    )

    print(
        f"Title: {script.get('title')}"
    )

    print(
        f"Scenes: {len(script['scenes'])}"
    )


    return script



def _generate_with_retry(
    client,
    prompt,
    max_attempts=4,
    base_delay=15
):

    """
    Gemini overload/error handling.
    """

    models_to_try = [

        "gemini-2.5-flash",

        "gemini-2.0-flash"
    ]


    last_error = None


    for model_name in models_to_try:


        for attempt in range(
            1,
            max_attempts + 1
        ):


            try:

                print(
                    f"Trying {model_name} "
                    f"attempt {attempt}/{max_attempts}"
                )


                return (
                    client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                )


            except genai_errors.ServerError as e:


                last_error = e


                print(
                    f"{model_name} failed "
                    f"on attempt {attempt}: {e}"
                )


                if attempt < max_attempts:


                    delay = (
                        base_delay
                        *
                        (
                            2
                            **
                            (
                                attempt - 1
                            )
                        )
                    )


                    print(
                        f"Retrying in "
                        f"{delay} seconds..."
                    )


                    time.sleep(
                        delay
                    )


            except genai_errors.ClientError:

                raise


        print(
            f"{model_name} unavailable."
        )

        print(
            "Trying fallback model..."
        )


    raise RuntimeError(

        "Gemini API failed after all retries "
        "and fallback models."

    ) from last_error

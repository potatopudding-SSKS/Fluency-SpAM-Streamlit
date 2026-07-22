import time
import random
import json
import os
import streamlit as st

try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

MONGO_URI = os.environ.get("MONGO_URI", "")   # set this in your environment


def save_to_mongo(participant_dict: dict) -> bool:
    """Returns True on success, False on failure."""
    if not MONGO_AVAILABLE:
        st.error("pymongo is not installed. Run: pip install pymongo")
        return False
    if not MONGO_URI:
        st.error("MONGO_URI environment variable is not set.")
        return False
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client["semantic_fluency_db"]
        col = db["participants"]
        col.insert_one(participant_dict)
        client.close()
        return True
    except Exception as exc:
        st.error(f"MongoDB error: {exc}")
        return False


ALL_CATEGORIES = ["body_parts", "fruitsnveg", "animals"]

CAT2HI = {
    "body_parts":   "शरीर के अंगों",
    "fruitsnveg":   "फल और सब्जियां",
    "animals":      "जानवरों",
}

VFT_DURATION_SECONDS = 10   # Should be 180 in the release version

SPAM_COMPONENT_HTML = """
<div class="spam-root">
    <div id="word-drop-area" class="spam-plane" aria-label="Placement plane" tabindex="0"></div>
    <div class="spam-actions">
        <button class="spam-continue" type="button">कंटिन्यू</button>
    </div>
</div>
"""

SPAM_COMPONENT_CSS = """
.spam-root {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-family: "Helvetica Neue", Arial, sans-serif;
    width: 100%;
    align-items: center;
}

.spam-plane {
    position: relative;
    margin: 24px auto 8px;
    width: min(100%, 960px);
    height: min(60vh, 560px);
    min-height: 360px;
    max-height: 680px;
    border: 2px solid #aaa;
    padding: 20px;
    overflow: hidden;
}

.spam-box {
    display: inline-block;
    background: #eef;
    color: #1a1a1a;
    padding: 4px 8px;
    border: 1px solid #aaa;
    border-radius: 4px;
    cursor: grab;
    user-select: none;
    font-size: 14px;
    line-height: 1.2;
    margin-bottom: 4px;
    white-space: nowrap;
}

.spam-box:active {
    cursor: grabbing;
}

.spam-actions {
    display: flex;
    justify-content: center;
    width: 100%;
}

.spam-continue {
    display: none;
    margin-top: 20px;
    background-color: #2e9f5e;
    color: white;
    font-size: 18px;
    font-weight: 600;
    padding: 12px 28px;
    border: none;
    border-radius: 6px;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    cursor: pointer;
}
"""

SPAM_COMPONENT_JS = """
export default function(component) {
    const { data, parentElement, setTriggerValue } = component;
    const words = Array.isArray(data?.words) ? data.words : [];

    const plane = parentElement.querySelector(".spam-plane");
    const continueButton = parentElement.querySelector(".spam-continue");
    if (!plane || !continueButton) {
        return;
    }

    const movedIds = new Set();

    function roundTo(value, digits) {
        const factor = Math.pow(10, digits);
        return Math.round(value * factor) / factor;
    }

    function clamp01(value) {
        return Math.min(1, Math.max(0, value));
    }

    function getCoords(element) {
        const dropRect = plane.getBoundingClientRect();
        const elemRect = element.getBoundingClientRect();
        if (dropRect.width === 0 || dropRect.height === 0) {
            return [0, 0];
        }
        const xPx = elemRect.left - dropRect.left;
        const yPx = elemRect.top - dropRect.top;
        const xCenter = xPx + elemRect.width / 2;
        const yCenter = yPx + elemRect.height / 2;
        const xNorm = clamp01(xCenter / dropRect.width);
        const yNorm = clamp01((dropRect.height - yCenter) / dropRect.height);
        return [roundTo(xNorm, 6), roundTo(yNorm, 6)];
    }

    function collectCoords() {
        const coords = {};
        plane.querySelectorAll(".spam-box").forEach((box) => {
            coords[box.dataset.word] = getCoords(box);
        });
        return coords;
    }

    function enableContinueIfReady() {
        if (movedIds.size === words.length) {
            continueButton.style.display = "inline-block";
        }
    }

    function draggable(element, onFirstMove) {
        let offsetX = 0;
        let offsetY = 0;
        let dragging = false;
        let hasMoved = false;

        element.addEventListener("pointerdown", (event) => {
            dragging = true;
            element.setPointerCapture(event.pointerId);
            const rect = element.getBoundingClientRect();
            offsetX = event.clientX - rect.left;
            offsetY = event.clientY - rect.top;
            element.style.cursor = "grabbing";
            event.preventDefault();
        });

        element.addEventListener("pointermove", (event) => {
            if (!dragging) {
                return;
            }
            const dropRect = plane.getBoundingClientRect();
            let left = event.clientX - dropRect.left - offsetX;
            let top = event.clientY - dropRect.top - offsetY;

            left = Math.max(0, Math.min(left, dropRect.width - element.offsetWidth));
            top = Math.max(0, Math.min(top, dropRect.height - element.offsetHeight));

            element.style.left = left + "px";
            element.style.top = top + "px";

            if (!hasMoved) {
                hasMoved = true;
                if (typeof onFirstMove === "function") {
                    onFirstMove();
                }
            }
        });

        function endDrag(event) {
            if (!dragging) {
                return;
            }
            dragging = false;
            element.releasePointerCapture(event.pointerId);
            element.style.cursor = "grab";
            if (!movedIds.has(element.dataset.wordId)) {
                movedIds.add(element.dataset.wordId);
                enableContinueIfReady();
            }
        }

        element.addEventListener("pointerup", endDrag);
        element.addEventListener("pointercancel", endDrag);
    }

    let currentIndex = 0;

    function nextWord() {
        if (currentIndex >= words.length) {
            return;
        }
        const word = words[currentIndex];
        const wordDiv = document.createElement("div");
        wordDiv.textContent = word;
        wordDiv.className = "spam-box";
        wordDiv.dataset.word = word;
        wordDiv.dataset.wordId = String(currentIndex);
        wordDiv.style.position = "absolute";
        wordDiv.style.left = "20px";
        wordDiv.style.top = "20px";

        plane.appendChild(wordDiv);
        draggable(wordDiv, () => {
            currentIndex += 1;
            setTimeout(() => {
                nextWord();
            }, 2000);
        });
    }

    continueButton.onclick = () => {
        if (movedIds.size !== words.length) {
            return;
        }
        setTriggerValue("continue_clicked", collectCoords());
    };

    while (plane.firstChild) {
        plane.removeChild(plane.firstChild);
    }
    continueButton.style.display = "none";
    movedIds.clear();
    currentIndex = 0;
    nextWord();
}
"""


def _build_steps():
    steps = [
        "consent",
        "gen_instructions",
        "vft_instructions",
        "vft_task_0",
        "spam_instructions",
        "spam_task_0",
        # "interval_1",
        # "vft_task_1",
        # "spam_task_1",
        # "interval_2",
        # "vft_task_2",
        # "spam_task_2",
        "exit_poll_instructions",
        "exit_poll_1",
        "exit_poll_2",
        "exit_poll_3",
        "exit_poll_4",
        "exit_poll_5",
        "exit_poll_6",
        "exit_poll_7",
        "exit_poll_8",
        "saving",
        "thank_you",
    ]
    return steps


# Session-state bootstrap
def _init():
    if "initialised" in st.session_state:
        return

    st.session_state.initialised = True
    st.session_state.steps = _build_steps()
    st.session_state.step_idx = 0

    # Randomised category order
    cat_order = ALL_CATEGORIES[:]
    random.shuffle(cat_order)
    st.session_state.cat_order = cat_order

    # Participant bag
    st.session_state.p = {
        "name": "",
        "rno": "",
        "categories": {},   # cat_name -> {"words_and_rts": [...], "words_and_coords": {...}}
    }

    # VFT live state
    st.session_state.vft_words_and_rts = []
    st.session_state.vft_start_time = None
    st.session_state.vft_end_time = None
    st.session_state.vft_timer_done = False
    st.session_state.vft_current_input = ""

    # Exit-poll intermediates
    st.session_state.lang_list = []


def advance():
    st.session_state.step_idx += 1
    # Reset VFT state whenever we enter a new vft_task step
    current = st.session_state.steps[st.session_state.step_idx]
    if current.startswith("vft_task_"):
        st.session_state.vft_words_and_rts = []
        st.session_state.vft_start_time = None
        st.session_state.vft_end_time = None
        st.session_state.vft_timer_done = False
        st.session_state.vft_current_input = ""


def current_step():
    return st.session_state.steps[st.session_state.step_idx]


def cat_for_step(step_name: str):
    """Return the category name for a vft_task_N or spam_task_N step."""
    idx = int(step_name.split("_")[-1])
    return st.session_state.cat_order[idx]


# Page config 
st.set_page_config(
    page_title="Semantic Fluency Test",
    page_icon=":brain:",
    layout="centered",
)

_init()
step = current_step()



# Consent
if step == "consent":
    st.header("Please read the following:")
    st.markdown(
"""
**This is a consent form for research participation.** It holds valuable information about this study and what to expect if you decide to participate.

**Your participation is voluntary.**

Please consider the information carefully. Feel free to ask questions before making your decision to participate. If you decide to participate, you will be asked to sign this form and will receive a copy of the form.

**Purpose:** The purpose of the study is to investigate semantic memory organization and verbal fluency patterns in Hindi speakers.

**Procedures/Tasks:** You need to have a good internet connection for this experiment. For the time being, you will have to participate in two tasks:

1. **Verbal Fluency Task:** You will be shown a category name and asked to type as many words as you can from that category within a time limit.
2. **Spatial Arrangement Task:** You will organize the words you typed by arranging them spatially based on how similar they are to each other.

Although no identifiable information will be published, the responses you provide should not have any sensitive information (e.g., relating to illegal behaviors, alcohol or drug use, sexual attitudes, mental health, etc.) nor should you disclose any information that may place you at risk of criminal or civil liability.

You will be asked to answer questions based on the information you supplied earlier and that concludes the task.

**Duration:** Participating in the data collection phase of the study should take up to 30 minutes of your time. You may leave the study at any time. If you decide to stop participating in the study, there will be no penalty to you and your decision will not affect your future relationship with IIIT-Hyderabad.

**Risks and Benefits:** There are minimal anticipated risks to you because of participating in this study and no long-term consequences are expected. No identifiable information will be published. The data will be kept in electronic form on a secure server. You will not benefit directly from participating in the study.

**Confidentiality:** Efforts will be made to keep your study-related information confidential. However, there may be circumstances where this information must be released. For example, personal information on your participation in this study may be disclosed if required by state law. Also, your records may be reviewed by the following groups (as applicable to the research):

- Office for Human Research Protections or other federal, state, or international regulatory agencies.
- The IIIT (International Institute of Information Technology) Review Board or Office of Responsible Research Practices.
- The sponsor, if any, or agency supporting the study.

**Participant Rights:** If you are a student or employee at IIIT-Hyderabad, your decision to participate will not affect your grades or employment status.

If you choose to participate in the study, you may drop participation at any time. By signing this form, you do not give up any personal legal rights you may have as a participant in this study.

An Institutional Review Board responsible for human subjects' research at International Institute of Information Technology, Hyderabad (IIIT-H) reviewed this research project and found it to be acceptable, according to applicable state and federal regulations and University policies designed to protect the rights and welfare of participants in research.

**Contacts and Questions**
For questions, concerns, or complaints about the study you may contact:

1. K S Sai Sankalp (Email: kssaisankalp.davey@research.iiit.ac.in) or
2. Vishnu Sreekumar (Email: vishnu.sreekumar@iiit.ac.in)

**Signing the consent form**
I have read (or someone has read to me) this form, and I am aware that I am being asked to participate in a research study. I have had the opportunity to ask questions and have had them answered to my satisfaction. I agree to participate in this study.

I am not giving up any legal rights by signing this form. I will be given a copy of this form.

By signing this form, I verify that I am 18 years of age or older.

"""
    )
    with st.form("consent_form", clear_on_submit=True):
        name = st.text_input("Name*")
        rno  = st.text_input("Roll No.*")
        submitted = st.form_submit_button("I agree and wish to continue")
    if submitted:
        if not name.strip() or not rno.strip():
            st.warning("Please enter both your name and roll number.")
            st.stop()
        st.session_state.p["name"] = name.strip()
        st.session_state.p["rno"]  = rno.strip()
        advance()
        st.rerun()



# General Instructions
elif step == "gen_instructions":
    st.text("इस प्रयोग में भाग लेने के लिए धन्यवाद!")
    st.title("इस प्रयोग में दो चरण हैं:")
    st.markdown("<u>प्रथम चरण में</u>, आपको एक कैटेगरी का नाम दिखाया जाएगा।", unsafe_allow_html=True)
    st.markdown(
        "आपको निर्धारित समय सीमा के भीतर उस कैटेगरी से संबंधित जितने संभव हो सकें, "
        "उतने शब्द **हिंदी में** टाइप करने होंगे। \n\n जैसे \"कुत्ता\" -> \"kutta\"।"
    )
    st.markdown(
        "<u>दूसरे चरण में</u>, आप पहले टाइप किए गए हर शब्द को ऐसे संगठित करें जिससे समान अर्थ वाले शब्द एक-दूसरे के ज़्यादा करीब हों।",
        unsafe_allow_html=True,
    )
    st.markdown(
        "इस एक्सपेरिमेंट में सिर्फ़ 4 \"ट्रायल\" होंगे, इसलिए कृपया जितना हो सके उतना सटीकता बनाए रखें।"
    )
    st.markdown(
        "टाइप करते समय अथवा वस्तुओं को संगठित करते समय, शीघ्रता की आवश्यकता नहीं है, सटीकता सबसे महत्वपूर्ण है।"
    )
    st.markdown("जब आप शुरू करने के लिए तैयार हों, **\"कंटिन्यू\" दबाएँ।**")
    if st.button("कंटिन्यू"):
        advance()
        st.rerun()



# VFT Instructions
elif step == "vft_instructions":
    vft_block = st.container()
    with vft_block:
        st.title("**आप अभी एक वर्बल फ्लुएंसी टास्क करने वाले हैं।**")
        st.markdown(
            "इस टास्क में आपको एक कैटेगरी का नाम दिखाया जाएगा (जैसे, जानवर)।"
        )
        st.markdown(
            "आपका काम है 3 मिनट में उस कैटेगरी से जुड़ी जितनी ज़्यादा चीज़ें आप सोच सकते हैं, "
            "उन्हें **हिंदी में** टाइप करना।"
        )
        st.markdown("जैसे \"कुत्ता\" -> \"kutta\"।")
        st.markdown("आपको यह काम चार अलग-अलग डोमेन पर चार बार करना होगा।")
        st.markdown("हर शब्द टाइप करने के बाद, अगला शब्द टाइप करने के लिए **ENTER** दबाएँ।")
        st.markdown("जब टाइमर खत्म हो जाएगा, तो आप अपने आप अगले टास्क पर चले जाएंगे।")
        st.markdown("जब आप तैयार हों, तो **शुरू दबाएँ!**")
        start_clicked = st.button("शुरू")
    if start_clicked:
        vft_block.empty()
        advance()
        st.rerun()



# VFT Task
elif step.startswith("vft_task_"):
    cat = cat_for_step(step)
    hi_cat = CAT2HI[cat]

    # Initialise timer on first render of this step
    if st.session_state.vft_end_time is None:
        st.session_state.vft_start_time = time.time()
        st.session_state.vft_end_time   = time.time() + VFT_DURATION_SECONDS
        st.session_state.vft_timer_done = False

    now       = time.time()
    remaining = max(0, int(st.session_state.vft_end_time - now))
    minutes, seconds = divmod(remaining, 60)

    st.title(f"**{hi_cat}** से जुड़ी जितनी ज़्यादा चीज़ों के नाम बता सकते हैं, बताएं।")
    st.markdown(
        f"<div style='font-size:28px;font-weight:700;'>⏱ {minutes:02d}:{seconds:02d}</div>",
        unsafe_allow_html=True,
    )

    # Input box (only while timer is running)
    if remaining > 0:
        def _on_enter():
            word = st.session_state.vft_current_input.strip()
            if word:
                rt = time.time() - st.session_state.vft_start_time
                st.session_state.vft_words_and_rts.append((word, round(rt, 3)))
            st.session_state.vft_current_input = ""

        st.text_input(
            label="हर शब्द के बाद **ENTER** दबाएँ! कृपया **अंग्रेज़ी अक्षरों** का उपयोग करके **हिंदी शब्द** लिखें।",
            key="vft_current_input",
            on_change=_on_enter,
        )
        # Auto-refresh every second to update the countdown
        time.sleep(1)
        st.rerun()
    else:
        # Timer expired
        st.info("समय समाप्त! आगे बढ़ने के लिए नीचे दबाएँ।")
        if st.button("अगली टास्क पर जाएं"):
            # Save data
            st.session_state.p["categories"][cat] = {
                "words_and_rts": st.session_state.vft_words_and_rts[:],
                "words_and_coords": {},
            }
            advance()
            st.rerun()



# SpAM Instructions
elif step == "spam_instructions":
    st.title("अब, आप एक स्पेशियल अरेंजमेंट टास्क शुरू करेंगे।")
    st.markdown(
        "इस टास्क में, आपको उन शब्दों का सेट दिखाया जाएगा "
        "जो आपने पिछले वर्बल फ्लुएंसी टास्क में टाइप किए थे।"
    )
    st.markdown(
        "हमें यह जानना है कि आपके अनुसार ये शब्द एक-दूसरे से कितने मिलते-जुलते हैं। "
        "आपका काम है हर शब्द को इस तरह मूव करना कि समान शब्द एक-दूसरे के करीब आ जाएं।"
    )
    st.markdown(
        "*(पास होने का मतलब है ज़्यादा समानता, दूर होने का मतलब है ज़्यादा असमानता)*"
    )
    st.markdown(
        "शब्द एक बॉक्स के ऊपरी बाएँ कोने में एक-एक करके दिखाई देंगे। "
        "बस उन्हें क्लिक और ड्रैग करके हिलाएँ।"
    )
    st.markdown(
        "हर शब्द को ड्रैग करने के बाद, 2 सेकंड में अगला शब्द आएगा। "
        "आप पहले से रखे गए शब्दों को फिर से व्यवस्थित कर सकते हैं।"
    )
    st.markdown(
        "**सभी** शब्दों को कम से कम एक बार हिलाने के बाद ही "
        "\"कंटिन्यू\" बटन दिखाई देगा।"
    )
    st.markdown("जब आप तैयार हों, तो **शुरू** दबाएँ।")
    if st.button("शुरू"):
        advance()
        st.rerun()



# SpAM Task
elif step.startswith("spam_task_"):
    cat   = cat_for_step(step)
    words = [
        w for w, _ in
        st.session_state.p["categories"].get(cat, {}).get("words_and_rts", [])
    ]

    if not words:
        st.warning("इस कैटेगरी में कोई शब्द नहीं मिले। अगले चरण पर जाएं।")
        if st.button("अगला"):
            advance()
            st.rerun()
        st.stop()

    st.title("शब्दों को नीचे दिए गए क्षेत्र में व्यवस्थित करें।")
    st.markdown(
        "हर शब्द को एक बार मूव करें - सभी शब्द मूव होने के बाद **कंटिन्यू** बटन दिखाई देगा।"
    )

    spam_component = st.components.v2.component(
            name="spam_plane",
            html=SPAM_COMPONENT_HTML,
            css=SPAM_COMPONENT_CSS,
            js=SPAM_COMPONENT_JS,
            isolate_styles=True,
    )

    result = spam_component(
            key=f"spam-plane-{cat}",
            data={"words": words},
            on_continue_clicked_change=lambda: None,
    )

    if result and result.continue_clicked:
            coords_raw = result.continue_clicked
            if isinstance(coords_raw, dict) and len(coords_raw) == len(words):
                    st.session_state.p["categories"][cat]["words_and_coords"] = {
                            word: (float(coords_raw[word][0]), float(coords_raw[word][1]))
                            for word in coords_raw
                    }
                    advance()
                    st.rerun()
            else:
                    st.warning("Coords mismatch - please try again.")



# Interval
elif step.startswith("interval_"):
    st.header("अब आप अगली कैटेगरी पर जाएंगे।")
    st.markdown(
        "याद दिलाने के लिए, इस टास्क में आपको बड़े अक्षरों में दी गई कैटेगरी से जुड़े "
        "जितने भी शब्द याद आएं, उन सभी को टाइप करना है।"
    )
    st.markdown("शुरू करने के लिए **शुरू** दबाएँ।")
    if st.button("शुरू"):
        advance()
        st.rerun()



# Exit Poll Instructions
elif step == "exit_poll_instructions":
    st.markdown("Now we would like to ask you some follow up questions")
    st.markdown("The questions marked by * are mandatory, those that are not can be left blank if you prefer not to answer them.")
    st.markdown("When you are ready, click the **Continue** button below to proceed.")
    if st.button("Continue"):
        advance()
        st.rerun()



# Exit Poll 1
elif step == "exit_poll_1":
    st.header("Exit Poll")
    opts = [
        "Most Uncomfortable",
        "Moderately Uncomfortable",
        "Neutral",
        "Moderately Comfortable",
        "Most Comfortable",
    ]
    strats_1 = st.text_area("What strategies, if any, did you use while attempting the task for Animals?")
    strats_2 = st.text_area("What strategies, if any, did you use while attempting the task for Body Parts?")
    strats_3 = st.text_area("What strategies, if any, did you use while attempting the task for Fruits and Vegetables?")
    strats_4 = st.text_area("What strategies, if any, did you use while attempting the task for Items found in a Marketplace")
    strats = [strats_1, strats_2, strats_3, strats_4]
    hi_r = st.radio("How comfortable are you with reading Hindi in Devanagari?*",  opts, horizontal=True)
    hi_w = st.radio("How comfortable are you with writing Hindi in the English alphabet?*", opts, horizontal=True)
    en_r = st.radio("How comfortable are you with reading English?*",  opts, horizontal=True)
    en_w = st.radio("How comfortable are you with writing English?*", opts, horizontal=True)
    if st.button("Continue"):
        st.session_state.p.update(
            strats=strats, hi_r=hi_r, hi_w=hi_w, en_r=en_r, en_w=en_w
        )
        advance()
        st.rerun()



# Exit Poll 2  - languages
elif step == "exit_poll_2":
    st.header("Follow Up Questions:")
    first_lang = st.text_input("What is your first language?*")
    lang_count  = st.number_input("How many languages do you know?*", min_value=1, step=1, value=1)

    def _add_lang():
        lang = st.session_state._lang_input.strip()
        if lang and lang not in st.session_state.lang_list:
            st.session_state.lang_list.append(lang)
        st.session_state._lang_input = ""

    st.text_input(
        "Enter each language you know and press **Enter**:",
        key="_lang_input",
        on_change=_add_lang,
    )
    if st.session_state.lang_list:
        st.write("Languages entered:", st.session_state.lang_list)

    if len(st.session_state.lang_list) >= int(lang_count):
        if st.button("Continue"):
            st.session_state.p["first_lang"]  = first_lang
            st.session_state.p["lang_count"]  = int(lang_count)
            st.session_state.p["lang_list"]   = st.session_state.lang_list[:]
            advance()
            st.rerun()
    else:
        remaining_langs = int(lang_count) - len(st.session_state.lang_list)
        st.info(f"Please enter {remaining_langs} more language(s).")



# Exit Poll 3  - language proficiency
elif step == "exit_poll_3":
    st.header("Follow Up Questions:")
    st.markdown(
        "For each language, rate your proficiency (1 = least, 5 = most proficient).*"
    )
    opts = ["1 - Least Proficient", "2", "3", "4", "5 - Most Proficient"]
    lang_prof = {}
    for lang in st.session_state.p.get("lang_list", []):
        lang_prof[lang] = st.radio(f"Proficiency in **{lang}**", opts, horizontal=True, key=f"prof_{lang}")
    if st.button("Continue"):
        st.session_state.p["lang_prof"] = lang_prof
        advance()
        st.rerun()



# Exit Poll 4  - language acquisition order
elif step == "exit_poll_4":
    st.header("Follow Up Questions:")
    st.markdown(
        "Rank each language by when you acquired it (1 = first language learnt).*"
    )
    opts = ["1 - First", "2", "3", "4", "5 - Last"]
    lang_order = {}
    for lang in st.session_state.p.get("lang_list", []):
        lang_order[lang] = st.radio(f"Order for **{lang}**", opts, horizontal=True, key=f"order_{lang}")
    if st.button("Continue"):
        st.session_state.p["lang_order"] = lang_order
        advance()
        st.rerun()



# Exit Poll 5  - location
elif step == "exit_poll_5":
    st.header("Follow Up Questions:")
    states_and_uts = [
        "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
        "Bihar",
        "Chandigarh", "Chhattisgarh",
        "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
        "Goa", "Gujarat",
        "Haryana", "Himachal Pradesh",
        "Jammu and Kashmir", "Jharkhand",
        "Karnataka", "Kerala",
        "Ladakh", "Lakshadweep",
        "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
        "Nagaland",
        "Odisha",
        "Puducherry",
        "Punjab",
        "Rajasthan",
        "Sikkim",
        "Tamil Nadu", "Telangana", "Tripura",
        "Uttar Pradesh", "Uttarakhand",
        "West Bengal",
    ]
    loc = st.selectbox("Which state or union territory of India are you from?*", states_and_uts)
    if st.button("Continue"):
        st.session_state.p["location"] = loc
        advance()
        st.rerun()



# Exit Poll 6  - gender / age / education
elif step == "exit_poll_6":
    st.header("Follow Up Questions:")
    gender = st.radio("What is your gender?*", ["Male", "Female", "Other/Prefer not to say"], horizontal=True)
    age    = st.number_input("What is your age?*", min_value=18, max_value=100, step=1)
    edu    = st.number_input(
        "Years of formal education completed? (High school graduation = 12)*",
        min_value=0, max_value=30, step=1,
    )
    if st.button("Continue"):
        st.session_state.p.update(gender=gender, age=int(age), edu=int(edu))
        advance()
        st.rerun()



# Exit Poll 7  - dominant hand / alertness
elif step == "exit_poll_7":
    st.header("Follow Up Questions:")
    dom_hand = st.radio("What is your dominant hand?", ["Right", "Left", "Both"], horizontal=True)
    alert_tod = st.radio(
        "At what time of day do you feel most alert?",
        ["Morning", "Afternoon", "Evening", "Night", "No Difference"],
        horizontal=True,
    )
    if st.button("Continue"):
        st.session_state.p.update(dom_hand=dom_hand, alert_time=alert_tod)
        advance()
        st.rerun()



# Exit Poll 8  - open-ended
elif step == "exit_poll_8":
    extra = st.text_area(
        "Is there any other information you would like to share that might have "
        "affected your performance? (e.g. lack of sleep, noisy environment)"
    )
    if st.button("Submit"):
        st.session_state.p["extra_info"] = extra
        advance()
        st.rerun()



# Saving
elif step == "saving":
    st.info("Saving your data, please wait...")
    doc = dict(st.session_state.p)
    doc["submitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    success = save_to_mongo(doc)
    if success:
        advance()
        st.rerun()
    else:
        st.error(
            "Error saving data. "
            "Please contact the researcher."
        )
        if st.button("Try Again"):
            st.rerun()



# Finis
elif step == "thank_you":
    st.balloons()
    st.title("Thank You!")
    st.markdown(
        "You have successfully completed the experiment. "
        "Your data has been saved securely."
    )
    st.markdown(
        "If you have any questions, feel free to contact the researcher at "
        "kssaisankalp.davey@research.iiit.ac.in"
    )
import os, sys
import gradio as gr
import regex as re
import random
import subprocess

from assets.i18n.i18n import I18nAuto

import elevenlabs

i18n = I18nAuto()

now_dir = os.getcwd()
sys.path.append(now_dir)

model_root = os.path.join(now_dir, "logs")
model_root_relative = os.path.relpath(model_root, now_dir)

names = [
    os.path.join(root, file)
    for root, _, files in os.walk(model_root_relative, topdown=False)
    for file in files
    if (
        file.endswith((".pth", ".onnx"))
        and not (file.startswith("G_") or file.startswith("D_"))
    )
]

indexes_list = [
    os.path.join(root, name)
    for root, _, files in os.walk(model_root_relative, topdown=False)
    for name in files
    if name.endswith(".index") and "trained" not in name
]

def change_choices():
    names = [
        os.path.join(root, file)
        for root, _, files in os.walk(model_root_relative, topdown=False)
        for file in files
        if (
            file.endswith((".pth", ".onnx"))
            and not (file.startswith("G_") or file.startswith("D_"))
        )
    ]

    indexes_list = [
        os.path.join(root, name)
        for root, _, files in os.walk(model_root_relative, topdown=False)
        for name in files
        if name.endswith(".index") and "trained" not in name
    ]
    return (
        {"choices": sorted(names), "__type__": "update"},
        {"choices": sorted(indexes_list), "__type__": "update"},
    )


def get_indexes():
    indexes_list = [
        os.path.join(dirpath, filename)
        for dirpath, _, filenames in os.walk(model_root_relative)
        for filename in filenames
        if filename.endswith(".index") and "trained" not in filename
    ]

    return indexes_list if indexes_list else ""


def match_index(model_file: str) -> tuple:
    model_files_trip = re.sub(r"\.pth|\.onnx$", "", model_file)
    model_file_name = os.path.split(model_files_trip)[
        -1
    ]

    if re.match(r".+_e\d+_s\d+$", model_file_name):
        base_model_name = model_file_name.rsplit("_", 2)[0]
    else:
        base_model_name = model_file_name

    sid_directory = os.path.join(model_root_relative, base_model_name)
    directories_to_search = [sid_directory] if os.path.exists(sid_directory) else []
    directories_to_search.append(model_root_relative)
    matching_index_files = []

    for directory in directories_to_search:
        for filename in os.listdir(directory):
            if filename.endswith(".index") and "trained" not in filename:
                name_match = any(
                    name.lower() in filename.lower()
                    for name in [model_file_name, base_model_name]
                )

                folder_match = directory == sid_directory

                if name_match or folder_match:
                    index_path = os.path.join(directory, filename)
                    updated_indexes_list = get_indexes()
                    if index_path in updated_indexes_list:
                        matching_index_files.append(
                            (
                                index_path,
                                os.path.getsize(index_path),
                                " " not in filename,
                            )
                        )
    if matching_index_files:
        matching_index_files.sort(key=lambda x: (-x[2], -x[1]))
        best_match_index_path = matching_index_files[0][0]
        return best_match_index_path

    return ""

def process_input(file_path):
    with open(file_path, "r") as file:
        file_contents = file.read()
    gr.Info(f"The text from the txt file has been loaded!")
    return file_contents, None


def run_tts_script(
    tts_text,
    tts_voice,
    f0up_key,
    filter_radius,
    index_rate,
    hop_length,
    f0method,
    output_tts_path,
    output_rvc_path,
    pth_file,
    index_path,
    api_key,
):
    infer_script_path = os.path.join("rvc", "infer", "infer.py")

    if os.path.exists(output_tts_path):
        os.remove(output_tts_path)

    if api_key:
        elevenlabs.set_api_key(api_key)
    
    tts = elevenlabs.generate(text=tts_text, voice=tts_voice, model="eleven_multilingual_v2")
    elevenlabs.save(tts, output_tts_path)

    print(f"TTS with {tts_voice} completed. Output TTS file: '{output_tts_path}'")

    command_infer = [
        "python",
        infer_script_path,
        *map(str, [
            f0up_key,
            filter_radius,
            index_rate,
            hop_length,
            f0method,
            output_tts_path,
            output_rvc_path,
            pth_file,
            index_path,
            "False",
            "False",
        ]),
    ]
    subprocess.run(command_infer)
    return f"Text {tts_text} synthesized successfully.", output_rvc_path


def applio_plugin():
    gr.Markdown("""
    ## Elevenlabs TTS Plugin
    This plugin allows you to use the Elevenlabs TTS model to synthesize text into speech. Remeber that elevenlabs is a multilingual TTS model, so you can use it to synthesize text in different languages.
    Languages supported by the model: Chinese, Korean, Dutch, Turkish, Swedish, Indonesian, Filipino, Japanese, Ukrainian, Greek, Czech, Finnish, Romanian, Russian, Danish, Bulgarian, Malay, Slovak, Croatian, Classic Arabic, Tamil, English, Polish, German, Spanish, French, Italian, Hindi and Portuguese.
    """)
    default_weight = random.choice(names) if names else ""
    with gr.Row():
        with gr.Row():
            model_file = gr.Dropdown(
                label=i18n("Voice Model"),
                choices=sorted(names, key=lambda path: os.path.getsize(path)),
                interactive=True,
                value=default_weight,
                allow_custom_value=True,
            )
            best_default_index_path = match_index(model_file.value)
            index_file = gr.Dropdown(
                label=i18n("Index File"),
                choices=get_indexes(),
                value=best_default_index_path,
                interactive=True,
                allow_custom_value=True,
            )
        with gr.Column():
            refresh_button = gr.Button(i18n("Refresh"))
            unload_button = gr.Button(i18n("Unload Voice"))

            unload_button.click(
                fn=lambda: ({"value": "", "__type__": "update"}),
                inputs=[],
                outputs=[model_file],
            )

            model_file.select(
                fn=match_index,
                inputs=[model_file],
                outputs=[index_file],
            )

    voices = elevenlabs.voices()
    voice_names = [voice.name for voice in voices]

    tts_voice = gr.Dropdown(
        label=i18n("TTS Voices"),
        choices=voice_names,
        interactive=True,
        value=None,
    )

    tts_text = gr.Textbox(
        label=i18n("Text to Synthesize"),
        placeholder=i18n("Enter text to synthesize"),
        lines=3,
    )

    gr.Markdown("If you use this feature too much, make sure to grab an API key from ElevenLabs. Simply visit https://elevenlabs.com/ to get yours. Need help? Check out this link: https://elevenlabs.io/docs/api-reference/text-to-speech#authentication")
    api_key = gr.Textbox(
        label=i18n("Optional API Key"),
        placeholder=i18n("Enter your API key (This is optional if you make a lot of requests)"),
        value="",
        interactive=True,
    )

    txt_file = gr.File(
        label=i18n("Or you can upload a .txt file"),
        type="filepath",
    )

    with gr.Accordion(i18n("Advanced Settings"), open=False):
        with gr.Column():
            output_tts_path = gr.Textbox(
                label=i18n("Output Path for TTS Audio"),
                placeholder=i18n("Enter output path"),
                value=os.path.join(now_dir, "assets", "audios", "tts_output.wav"),
                interactive=True,
            )

            output_rvc_path = gr.Textbox(
                label=i18n("Output Path for RVC Audio"),
                placeholder=i18n("Enter output path"),
                value=os.path.join(now_dir, "assets", "audios", "tts_rvc_output.wav"),
                interactive=True,
            )

            pitch = gr.Slider(
                minimum=-24,
                maximum=24,
                step=1,
                label=i18n("Pitch"),
                value=0,
                interactive=True,
            )
            filter_radius = gr.Slider(
                minimum=0,
                maximum=7,
                label=i18n(
                    "If >=3: apply median filtering to the harvested pitch results. The value represents the filter radius and can reduce breathiness"
                ),
                value=3,
                step=1,
                interactive=True,
            )
            index_rate = gr.Slider(
                minimum=0,
                maximum=1,
                label=i18n("Search Feature Ratio"),
                value=0.75,
                interactive=True,
            )
            hop_length = gr.Slider(
                minimum=1,
                maximum=512,
                step=1,
                label=i18n("Hop Length"),
                value=128,
                interactive=True,
            )
        with gr.Column():
            f0method = gr.Radio(
                label=i18n("Pitch extraction algorithm"),
                choices=[
                    "pm",
                    "harvest",
                    "dio",
                    "crepe",
                    "crepe-tiny",
                    "rmvpe",
                ],
                value="rmvpe",
                interactive=True,
            )

    convert_button1 = gr.Button(i18n("Convert"))

    with gr.Row():
        vc_output1 = gr.Textbox(label=i18n("Output Information"))
        vc_output2 = gr.Audio(label=i18n("Export Audio"))

    refresh_button.click(
        fn=change_choices,
        inputs=[],
        outputs=[model_file, index_file],
    )
    txt_file.upload(
        fn=process_input,
        inputs=[txt_file],
        outputs=[tts_text, txt_file],
    )
    convert_button1.click(
        fn=run_tts_script,
        inputs=[
            tts_text,
            tts_voice,
            pitch,
            filter_radius,
            index_rate,
            hop_length,
            f0method,
            output_tts_path,
            output_rvc_path,
            model_file,
            index_file,
            api_key,
        ],
        outputs=[vc_output1, vc_output2],
    )

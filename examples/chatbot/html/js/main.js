let websocket_uri = 'ws://' + window.location.host + '/transcription';
let websocket_audio_uri = 'ws://' + window.location.host + '/audio';
let websocket_llm_uri = 'ws://' + window.location.host + '/llm'

let bufferSize = 4096,
    AudioContext,
    context,
    processor,
    input,
    websocket;
var intervalFunction = null;
var recordingTime = 0;
var server_state = 0;
var websocket_audio = null;
let audioContext_tts = null;
var you_name = "Jakub"

var audioContext = null;
var audioWorkletNode = null;
var audio_state = 0;
var available_transcription_elements = 0;
var available_llm_elements = 0;
var available_audio_elements = 0;
var llm_outputs = [];
var new_transcription_element_state = true;
var new_llm_element_state = true;
var audio_sources = [];
var audio_streams = [];
var audio_source = null;
var audio_playing = false;
var current_message_id = -1;
var currently_playing = null;
var blacklist = [];
var unique_id = null;
var input_language = "en";
var output_language = "en";
var tts_sampling_rate = 24000;
var micOn = false;
var audioQueueState = 0;


let languageMap = {}
languageMap['English'] = 'en';
languageMap['French'] = 'fr';
languageMap['Mandarin'] = 'zh';
languageMap['Spanish'] = 'es';
languageMap['Japanese'] = 'ja';

initWebSocket();

function toggleMic() {
    const controlContainer = document.getElementById('control-container');
    controlContainer.classList.toggle('active');
    if (!micOn) {
        startRecording();
        micOn = true;
    }
    else if (audio_state == 0) {
        stopRecording();
        current_message_id++;
        audio_streams = audio_streams.filter(a => a[0] !== current_message_id)
        if (audio_playing) {
            currently_playing.stop();
            audio_playing = false;
        }
    }
    else {
        audio_state = 0;
    }
    
}

// Function to toggle dropdown visibility
function toggleDropdown(dropdownId) {
    var dropdown = document.getElementById(dropdownId);
    dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
}

function onAudioOutputChange() {
    if (output_language != 'en') {
        tts_sampling_rate = 40000
    }
    else {
        tts_sampling_rate = 24000
    }
}

// Function to select a language and update the button text
function onInputChange(val) {
    input_language = languageMap[val];

    websocket.send(JSON.stringify({
        input_language: input_language,
        output_language: output_language,
    }));

    console.log("INPUT CHANGE: " + input_language)

}

function onOutputChange(val) {
    output_language = languageMap[val];
    websocket.send(JSON.stringify({
        input_language: input_language,
        output_language: output_language,
    }));
    onAudioOutputChange()
    console.log("OUTPUT CHANGE: " + output_language)
    console.log("AUDIO SAMPLING CHANGED TO: " + tts_sampling_rate)
}


const zeroPad = (num, places) => String(num).padStart(places, '0')

const generateUUID = () => {
    let dt = new Date().getTime();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (dt + Math.random() * 16) % 16 | 0;
        dt = Math.floor(dt / 16);
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
};

function recording_timer() {
    recordingTime++;
    document.getElementById("recording-time").innerHTML = zeroPad(parseInt(recordingTime / 60), 2) + ":" + zeroPad(parseInt(recordingTime % 60), 2) + "s";
}

const start_recording = async () => {
    console.log(audioContext)
    try {
        if (audioContext) {
            
            await audioContext.resume();
            
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            if (!audioContext) return;
            console.log(audioContext?.state);

            await audioContext.audioWorklet.addModule("js/audio-processor.js");

            const source = audioContext.createMediaStreamSource(stream);
            audioWorkletNode = new AudioWorkletNode(audioContext, "audio-stream-processor");

            audioWorkletNode.port.onmessage = (event) => {
                if (server_state != 1) {
                  console.log("server is not ready!!")
                  return;
                }
                const audioData = event.data;
                if (websocket && websocket.readyState === WebSocket.OPEN && audio_state == 0 && audioQueueState == 0) {
                    websocket.send(audioData.buffer);
                    console.log("send data")
                }
            };

            source.connect(audioWorkletNode);
        }
    } catch (e) {
        console.log("Error", e);
    }
};

const handleStartRecording = async () => {
    start_recording();
};

const startRecording = async () => {
    // document.getElementById("instructions-text").style.display = "none";
    // document.getElementById("control-container").style.backgroundColor = "white";

    AudioContext = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioContext({ latencyHint: 'interactive', sampleRate: 16000 });

    audioContext_tts = new AudioContext({ sampleRate: tts_sampling_rate });

    // document.getElementById("recording-stop-btn").style.display = "block";
    // document.getElementById("recording-dot").style.display = "block";
    // document.getElementById("recording-line").style.display = "block";
    // document.getElementById("recording-time").style.display = "block";
    
    // intervalFunction = setInterval(recording_timer, 1000);

    await handleStartRecording();
};

function stopRecording() {
    audio_state = 1;
    // clearInterval(intervalFunction);
}

function initWebSocket() {

    websocket = new WebSocket(websocket_uri);
    websocket.binaryType = "arraybuffer";

    console.log("Websocket created.");
  
    websocket.onopen = function() {
      console.log("Connected to server.");
      unique_id = generateUUID()
      websocket.send(JSON.stringify({
        uid: unique_id,
        multilingual: false,
        input_language: input_language,
        output_language: output_language,
        task: "transcribe"
      }));
    }
    
    websocket.onclose = function(e) {
      console.log("Connection closed (" + e.code + ").");
    }
    
    websocket.onmessage = function(e) {
      var data = JSON.parse(e.data);

      if ("message" in data) {
        if (data["message"] == "SERVER_READY") {
            server_state = 1;
        }
      } else if ("segments" in data) {
        if (new_transcription_element_state) {
            current_message_id++;
            audio_streams = audio_streams.filter(a => a[0] !== current_message_id)
            if (audio_playing) {
                currently_playing.stop();
                audio_playing = false;
            }
            available_transcription_elements = available_transcription_elements + 1;

            var img_src = "0.png";
            if (you_name.toLowerCase() == "marcus") {
                you_name = "Marcus";
                img_src = "0.png";
            } else if (you_name.toLowerCase() == "vineet") {
                you_name = "Vineet";
                img_src = "1.png";
            } else if (you_name.toLowerCase() == "jakub") {
                you_name = "Jakub";
                img_src = "2.png";
            }

            new_transcription_element(you_name, img_src);
            new_text_element("<p>" +  data["segments"][0].text + "</p>", "transcription-" + available_transcription_elements);
            new_transcription_element_state = false;
            
        }
        document.getElementById("transcription-" + available_transcription_elements).innerHTML = "<p>" + data["segments"][0].text + "</p>"; 

        if (data["eos"] == true) {
            new_transcription_element_state = true;
            audioQueueState = 1;
        }
      } else if ("llm_output" in data) {

            if (new_llm_element_state) {
                available_llm_elements = available_llm_elements + 1
                new_transcription_element("AT&T GLM-4", "1.png");
                new_text_element("<p>" +  data["llm_output"] + "</p>", "llm-" + available_llm_elements);
                new_llm_element_state = false;
            }
            document.getElementById("llm-" + available_llm_elements).innerHTML = "<p>" + data["llm_output"] + "</p>"; 

            if (data["eos"] == true) {
                new_llm_element_state = true;
            }
      }

      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }


    websocket_audio = new WebSocket(websocket_audio_uri);
    websocket_audio.binaryType = "arraybuffer";

    websocket_audio.onopen = function() { 
        console.log("Connected to websocket audio")
        websocket_audio.send(JSON.stringify({
            id: unique_id
          }));
    }
    websocket_audio.onclose = function(e) { }
    websocket_audio.onmessage = function (e) {
        audioQueueState = 0;
        available_audio_elements++;
        // var data = JSON.parse(e.data);
        
        let float32Array = new Float32Array(e.data);
        const uint8 = new Uint8Array(e.data)
        let message_id = Math.floor(uint8[3]);
        
        console.log("message_id: " + message_id);
        console.log("current_message_id: " + current_message_id);
        console.log("Blacklist: " + blacklist);
        if (message_id < current_message_id) {
            return
        }
        let audioBuffer = audioContext_tts.createBuffer(1, float32Array.length, tts_sampling_rate);
        audioBuffer.getChannelData(0).set(float32Array);

        //new_whisper_speech_audio_element("audio-" + available_audio_elements, Math.floor(audioBuffer.duration));

       // audio_sources.push(audioBuffer);

        audio_source = audioContext_tts.createBufferSource();
        audio_source.buffer = audioBuffer;
        audio_source.connect(audioContext_tts.destination);
        audio_source.addEventListener('ended', () => {
            if (audio_streams.length > 0) {
                currently_playing = audio_streams.shift()[1];
                currently_playing.start();
                audio_playing = true
            } else {
                currently_playing = null;
                audio_playing = false;
                current_message_id++;
            }
            
        });
        console.log("Audio_playing: " + audio_playing);
        if (!audio_playing) {
            currently_playing = audio_source;
            currently_playing.start();
            audio_playing = true;
        } else {
            console.log(audio_source + " added to queueu");
            audio_streams.push([message_id, audio_source]);
        }
        
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }

    websocket_llm = new WebSocket(websocket_llm_uri);
    websocket_llm.binaryType = "arraybuffer";
    websocket_llm.onopen = function() {
        console.log("Connected to server.");
        
        websocket_llm.send(JSON.stringify({
          uid: unique_id,
        }));
      }

    console.log("LLm websocket created");
}

function new_transcription_element(speaker_name, speaker_avatar) {
    var avatar_container = document.createElement("div");
    avatar_container.className = "avatar-container";

    var avatar_img = document.createElement("div");
    avatar_img.innerHTML = "<img class='avatar' src='img/" + speaker_avatar + "' \>";

    var avatar_name = document.createElement("div");
    avatar_name.className = "avatar-name";
    avatar_name.innerHTML = speaker_name;

    var dummy_element = document.createElement("div");

    avatar_container.appendChild(avatar_img);
    avatar_container.appendChild(avatar_name);
    avatar_container.appendChild(dummy_element);

    document.getElementById("main-wrapper").appendChild(avatar_container);
}

function new_text_element(text, id) {
    var text_container = document.createElement("div");
    text_container.className = "text-container";
    text_container.style.maxWidth = "500px";

    var text_element = document.createElement("div");
    text_element.id = id;
    text_element.innerHTML = "<p>" + text + "</p>";

    var dummy_element = document.createElement("div");
    console.log("THIS IS CONSOLE LOG" + text);

    text_container.appendChild(text_element);
    text_container.appendChild(dummy_element);

    document.getElementById("main-wrapper").appendChild(text_container);
}

function new_transcription_time_element(time) {
    var text_container = document.createElement("div");
    text_container.className = "transcription-timing-container";
    text_container.style.maxWidth = "500px";

    var text_element = document.createElement("div");
    text_element.innerHTML = "<span>WhisperLive - Transcription time: " + time + "ms</span>";

    var dummy_element = document.createElement("div");

    text_container.appendChild(text_element);
    text_container.appendChild(dummy_element);

    document.getElementById("main-wrapper").appendChild(text_container);
}

function new_llm_time_element(time) {
    var text_container = document.createElement("div");
    text_container.className = "llm-timing-container";
    text_container.style.maxWidth = "500px";

    var first_response_text_element = document.createElement("div");
    first_response_text_element.innerHTML = "<span>Phi-2 first response time: " + time + "ms</span>";

    var complete_response_text_element = document.createElement("div");
    complete_response_text_element.innerHTML = "<span>Phi-2 complete response time: " + time + "ms</span>";

    var dummy_element = document.createElement("div");

    text_container.appendChild(first_response_text_element);
    text_container.appendChild(complete_response_text_element);
    text_container.appendChild(dummy_element);

    document.getElementById("main-wrapper").appendChild(text_container);
}

function new_whisper_speech_audio_element(id, duration) {
    var audio_container = document.createElement("div");
    audio_container.className = "whisperspeech-audio-container";
    audio_container.style.maxWidth = "500px";

    var audio_div_element = document.createElement("div");
    var audio_element = document.createElement("audio");
    audio_element.style.paddingTop = "20px";

    if (duration > 10)
        duration = 10;
    audio_element.src = "static/" + duration + ".mp3";

    audio_element.id = id;
    audio_element.onplay = function() {
        console.log(this.id)
        var id = this.id.split("-")[1] - 1;

        if (audio_source) {
            audio_source.disconnect();
        }
        audio_source = audioContext_tts.createBufferSource();
        audio_source.buffer = audio_sources[id];
        audio_source.connect(audioContext_tts.destination);
        audio_source.start()
    };
    audio_element.onpause = function() {
        this.currentTime = 0;
        console.log(this.id)
        var id = this.id.split("-")[1] - 1;
        if (audio_source) {
            audio_source.stop();
        }
    };
    audio_element.controls = true;

    audio_div_element.appendChild(audio_element);

    var dummy_element_a = document.createElement("div");
    var dummy_element_b = document.createElement("div");

    audio_container.appendChild(dummy_element_a);
    audio_container.appendChild(audio_div_element);
    audio_container.appendChild(dummy_element_b);

    document.getElementById("main-wrapper").appendChild(audio_container);
}

function new_whisper_speech_time_element(time) {
    var text_container = document.createElement("div");
    text_container.className = "whisperspeech-timing-container";
    text_container.style.maxWidth = "500px";

    var text_element = document.createElement("div");
    text_element.innerHTML = "<span>WhisperSpeech response time: " + time + "ms</span>";

    var dummy_element = document.createElement("div");

    text_container.appendChild(text_element);
    text_container.appendChild(dummy_element);

    document.getElementById("main-wrapper").appendChild(text_container);
}

document.addEventListener('DOMContentLoaded', function() {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    if (urlParams.has('name')) {
        you_name = urlParams.get('name')
    }
 }, false);
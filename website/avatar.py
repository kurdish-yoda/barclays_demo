from flask import jsonify, Blueprint, request, current_app, session
import azure.cognitiveservices.speech as speechsdk
from typing import List, Dict
import base64
from .secrets import get_secret
import time

animation_bp = Blueprint('animation', __name__)

class SpeechSynthesizer:
    def __init__(self):
        self.speech_key = get_secret('KEY1-SPEECH')
        self.speech_region = get_secret('SPEECH-LOCATION')

        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech credentials not found in environment variables")

        self.synthesizer = None
        self.viseme_data = []
        self.total_bytes = 0
        self.stream_start_time = None
        self.packet_count = 0

    def initialize_sdk(self):
        try:
            if self.synthesizer:
                self.synthesizer.viseme_received.disconnect_all()
                self.synthesizer = None
            self.viseme_data = []

            speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
            speech_config.speech_synthesis_voice_name = session.get('voice')
            speech_config.speech_synthesis_voice_rate = session.get('speechSynthesisVoiceRate')
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
            )
            speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_RequestSentenceBoundary, "true")
            speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_RequestWordBoundary, "true")

            self.synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            self.synthesizer.viseme_received.connect(self.viseme_cb)
            self.synthesizer.synthesizing.connect(self.stream_status_cb)
            self.synthesizer.synthesis_started.connect(self.synthesis_started_cb)
            self.synthesizer.synthesis_completed.connect(self.synthesis_completed_cb)

        except Exception as e:
            current_app.logger.error(f"Error initializing Speech SDK: {str(e)}")
            raise

    def viseme_cb(self, evt):
        self.viseme_data.append({
            'offset': evt.audio_offset / 10000,  # Convert to milliseconds
            'visemeId': evt.viseme_id
        })
        # Log length of viseme data
        current_app.logger.debug(f'Viseme callback received. Current viseme data length: {len(self.viseme_data)}')

    def synthesize_speech(self, text: str):
        """
        Synthesizes speech from text and synchronizes the visemes for animation.
        """
        if not self.synthesizer:
            self.initialize_sdk()

        self.viseme_data = []  # Reset viseme data for new synthesis
        current_app.logger.debug("Viseme data reset for new synthesis")
        result = self.synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            current_app.logger.debug('Speech synthesis completed successfully.')
            return self.process_synthesis_result(result)
        else:
            current_app.logger.error(f"Speech synthesis failed: {result.reason}")
            raise Exception(f"Speech synthesis failed: {result.reason}")

    def process_synthesis_result(self, result):
        """
        Process the viseme data and return the synthesized result with animation.
        """
        current_app.logger.debug("Processing synthesis result.")
        processed_visemes = []
        if self.viseme_data:
            last_included_viseme = self.viseme_data[0]
            processed_visemes.append(last_included_viseme)

            min_viseme_duration = 75
            #min_viseme_duration = 200

            for current_viseme in self.viseme_data[1:]:
                duration_since_last = current_viseme['offset'] - last_included_viseme['offset']
                if duration_since_last >= min_viseme_duration:
                    processed_visemes.append(current_viseme)
                    last_included_viseme = current_viseme

        animation_data = {
            'frames': [
                {
                    'timestamp': v['offset'],
                    'viseme_id': v['visemeId'],
                    'image': f"{v['visemeId']}.png"
                } for v in processed_visemes
            ],
            'total_duration': processed_visemes[-1]['offset'] + 120 if processed_visemes else 0
        }

        self.clear_viseme_data()  # Clear viseme data after processing
        current_app.logger.debug("Processed viseme data cleared.")
        return {
            'audio': result.audio_data,
            'animation': animation_data
        }

    def clear_viseme_data(self):
        """
        Clears stored viseme data and properly closes all connections
        """
        try:
            self.viseme_data = []
            current_app.logger.debug("Clearing viseme data")

            if self.synthesizer:
                self.synthesizer.viseme_received.disconnect_all()
                self.synthesizer.synthesizing.disconnect_all()
                self.synthesizer.synthesis_started.disconnect_all()
                self.synthesizer.synthesis_completed.disconnect_all()
                self.synthesizer.stop_speaking_async()

                self.synthesizer = None

            current_app.logger.info("Speech synthesizer and viseme data cleared successfully.")
            return True

        except Exception as e:
            current_app.logger.error(f"Error during viseme cleanup: {str(e)}")
            return False

    def stream_status_cb(self, evt):
        """Tracks ongoing synthesis stream status"""
        self.packet_count += 1
        packet_size = len(evt.result.audio_data)
        self.total_bytes += packet_size

        # Only log every 10th packet to reduce verbosity
        if self.packet_count % 10 == 0:
            elapsed = time.time() - self.stream_start_time if self.stream_start_time else 0
            rate = self.total_bytes / (1024 * elapsed) if elapsed > 0 else 0
            current_app.logger.info(f"Streaming progress: {self.total_bytes / 1024:.2f}KB @ {rate:.2f}KB/s")

    def synthesis_started_cb(self, evt):
        """Logs when synthesis stream starts"""
        self.stream_start_time = time.time()
        current_app.logger.info("Speech synthesis stream started")

    def synthesis_completed_cb(self, evt):
        """Logs synthesis completion metrics"""
        if self.stream_start_time:
            duration = time.time() - self.stream_start_time
            total_kb = self.total_bytes / 1024
            rate = total_kb / duration if duration > 0 else 0

            current_app.logger.info(
                f"Synthesis completed:\n"
                f"  Duration: {duration:.2f}s\n"
                f"  Packets: {self.packet_count}\n"
                f"  Total size: {total_kb:.2f}KB\n"
                f"  Average rate: {rate:.2f}KB/s"
            )

            self.packet_count = 0
            self.total_bytes = 0
            self.stream_start_time = None

@animation_bp.route('/api/speech/synthesize', methods=['POST'])
def synthesize_speech():
    cleanup_synthesizer = SpeechSynthesizer()
    cleanup_synthesizer.clear_viseme_data()

    if not request.is_json:
        current_app.logger.error("Request content type is not JSON")
        return jsonify({'error': 'Content type must be application/json'}), 415

    text = request.json.get('text')
    if not text:
        current_app.logger.error("No text provided in request")
        return jsonify({'error': 'No text provided'}), 400

    try:
        synthesizer = SpeechSynthesizer()
        result = synthesizer.synthesize_speech(text)
        audio_base64 = base64.b64encode(result['audio']).decode('utf-8')

        # Increment playStop counter
        if 'user_metrics' not in session:
            session['user_metrics'] = {}
        if 'playStopPressesCoach' not in session['user_metrics']:
            session['user_metrics']['playStopPressesCoach'] = 0
        session['user_metrics']['playStopPressesCoach'] += 1
        session.modified = True

        response_data = {
            'animation': result['animation'],
            'audio': audio_base64
        }
        current_app.logger.debug("Synthesize speech response prepared.")
        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"Error during speech synthesis: {str(e)}")
        return jsonify({'error': str(e)}), 500

class AnimationController:
    # Viseme mapping - moved from frontend
    VISEME_MAP = {
        0: '0.png',   # Neutral mouth shape
        1: '1.png',   # "AE", "AX", "AH"
        2: '2.png',   # "AA"
        3: '3.png',   # "AO"
        4: '4.png',   # "EH", "AX"
        5: '5.png',   # "EY", "AY"
        6: '6.png',   # "IH", "IX"
        7: '7.png',   # "IY"
        8: '8.png',   # "UH", "UW"
        9: '9.png',   # "OW"
        10: '10.png', # "AW"
        11: '11.png', # "OY"
        12: '12.png', # "ER"
        13: '13.png', # "AX" (schwa)
        14: '14.png', # "S", "Z"
        15: '15.png', # "SH", "CH"
        16: '16.png', # "TH", "DH"
        17: '17.png', # "F", "V"
        18: '18.png', # "P", "B", "M"
        19: '19.png', # "K", "G", "NG"
        20: '20.png', # "R"
        21: '21.png'  # "L"
    }

    def __init__(self):
        self.min_viseme_duration = 75  # Minimum duration in milliseconds
        self.timing_offset = -10       # Timing offset for animations

    def process_viseme_data(self, viseme_data: List[Dict]) -> Dict:
        """
        Process viseme data and generate animation timeline
        """
        if not viseme_data:
            return {"error": "No viseme data provided"}

        processed_visemes = []
        last_included_viseme = viseme_data[0]
        processed_visemes.append(last_included_viseme)

        # Process visemes with minimum duration logic
        for current_viseme in viseme_data[1:]:
            duration_since_last = current_viseme['offset'] - last_included_viseme['offset']
            if duration_since_last >= self.min_viseme_duration:
                processed_visemes.append(current_viseme)
                last_included_viseme = current_viseme

        # Calculate animation timeline
        animation_timeline = self._generate_animation_timeline(processed_visemes)
        return animation_timeline

    def _generate_animation_timeline(self, processed_visemes: List[Dict]) -> Dict:
        """
        Generate the complete animation timeline including mouth and head movements
        """
        start_time = processed_visemes[0]['offset']
        animation_frames = []

        for viseme in processed_visemes:
            relative_delay = max(viseme['offset'] - start_time + self.timing_offset, 0)
            frame = {
                'timestamp': relative_delay,
                'viseme_id': viseme['visemeId'],
                'image': self.VISEME_MAP.get(viseme['visemeId'], '0.png')
            }
            animation_frames.append(frame)

        # Calculate total duration
        last_viseme = processed_visemes[-1]
        total_duration = last_viseme['offset'] - start_time + 120

        return {
            'frames': animation_frames,
            'total_duration': max(total_duration, self.min_viseme_duration + 120),
            'start_time': start_time
        }

@animation_bp.route('/api/speech/cleanup', methods=['POST'])
def cleanup_speech():
    try:
        synthesizer = SpeechSynthesizer()
        success = synthesizer.clear_viseme_data()

        if success:
            return jsonify({'status': 'success', 'message': 'Cleanup completed successfully'})
        else:
            return jsonify({'status': 'warning', 'message': 'Cleanup completed with warnings'}), 207

    except Exception as e:
        current_app.logger.error(f"Error during cleanup: {str(e)}")
        return jsonify({'error': str(e)}), 500

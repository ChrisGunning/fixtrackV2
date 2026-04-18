from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from scipy import signal
import numpy as np
import subprocess

vidPath1 = ''
vidPath2 = ''
exportPath = ''
scale = 5

# THIS FILE IS NOT YET FULLY INTEGRATED WITH THE APPLICATION

folderPath = exportPath


# Loads the audio and returns the audio data as well as the framerate
def _loadAudio(file_path):
    audio_segment = AudioSegment.from_file(file_path)
    data = np.array(audio_segment.get_array_of_samples())
    if audio_segment.channels > 1:
        data = data.reshape((-1, audio_segment.channels)).mean(axis=1)
    rate = audio_segment.frame_rate
    return data, rate


# Finds loudest point in audio
def _find_loudest_point(audio_data, frame_rate):
    loudest_index = np.argmax(np.abs(audio_data))
    start_time = loudest_index / frame_rate
    return start_time


# Finds offset of the 2 audios. This is recorded as the # of frames audio2 lags
def findOffset(vidPath1, vidPath2):
    audio1, rate1 = _loadAudio(vidPath1)
    audio2, rate2 = _loadAudio(vidPath2)
    correlation = signal.correlate(audio2, audio1, mode="full")
    lags = signal.correlation_lags(audio2.size, audio1.size, mode="full")
    lag = lags[np.argmax(correlation)]
    return lag


# Trims the video based off of the lag and frame_rate
def trim_video(video, output_file, lag, duration=None):
    time = f'00:00:0{lag:.3f}'
    hours = int(duration // 3600) if duration else 0
    minutes = int((duration % 3600) // 60) if duration else 0
    seconds = int(duration % 60) if duration else 0
    milliseconds = int((duration % 1) * 1000) if duration else 0
    duration_time = f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
    print(duration_time)

    if duration:
        command = [
            'ffmpeg', '-ss', time, '-y', '-i', video, '-c', 'copy', '-t', duration_time,
            output_file
        ]
    else:
        command = ['ffmpeg', '-ss', time, '-y', '-i', video, '-c', 'copy', output_file]

    subprocess.run(command)


def get_video_duration(video):
    clip = VideoFileClip(video)
    duration = clip.duration
    clip.close()
    return duration


# Load Audio Files and find lag
def update_offset(additional_offset=0, sameLength=False):
    global figure_title
    global offset
    global audio1
    global audio2
    global lag, rate1, vid1_altered, vid2_altered

    start_lag = lag / rate1 + additional_offset
    print('start_lag')
    print(start_lag)

    # AUDIO 2 delayed / Video 2 altered
    if start_lag > 0:
        print('video 2 altered')
        min_duration = None
        print(vidPath1)

        if not sameLength:
            duration1 = get_video_duration(vidPath1)
            duration2 = get_video_duration(vidPath2) - start_lag
            min_duration = min(duration1, duration2)

        trim_video(vidPath2, vid2_altered, start_lag, min_duration)
        print('trimming video 1 ------------------------------')
        trim_video(vidPath1, vid1_altered, 0, min_duration)
        audio2 = audio2[abs(int(lag)):]
        figure_title = vidPath1

    # AUDIO 2 Ahead / Video 1 Altered
    else:
        print('video 1 altered')
        min_duration = None

        if not sameLength:
            duration1 = get_video_duration(vidPath1) + start_lag
            duration2 = get_video_duration(vidPath2)
            min_duration = min(duration1, duration2)

        trim_video(vidPath1, vid1_altered, -start_lag, min_duration)
        trim_video(vidPath2, vid2_altered, 0, min_duration)
        audio1 = audio1[abs(int(lag)):]
        figure_title = vidPath2

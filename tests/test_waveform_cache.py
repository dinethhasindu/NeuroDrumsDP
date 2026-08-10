import numpy as np
from audio.waveform_cache import WaveformCache

def test_waveform_cache_build_and_slice(tmp_path):
    sr=1000; y=np.sin(np.linspace(0,20,5000)).astype('float32')
    c=WaveformCache(str(tmp_path)); c.build(y,sr,'test.wav')
    t,mn,mx=c.get_peaks(0,5,500)
    assert len(t)>0 and len(mn)==len(mx)==len(t)
    c2=WaveformCache(str(tmp_path)); c2.build(y,sr,'test.wav')
    assert abs(c2.duration-5.0)<1e-6

def test_cache_invalidates_on_length_change(tmp_path):
    c=WaveformCache(str(tmp_path)); c.build(np.zeros(1000,dtype='float32'),1000,'same.wav')
    c2=WaveformCache(str(tmp_path)); c2.build(np.zeros(2000,dtype='float32'),1000,'same.wav')
    assert abs(c2.duration-2.0)<1e-6

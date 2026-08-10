def export_mix(y, sr, path, bit_depth=24):
    import soundfile as sf
    subtype = {16:'PCM_16',24:'PCM_24',32:'FLOAT'}.get(bit_depth,'PCM_24')
    sf.write(path, y, sr, subtype=subtype)

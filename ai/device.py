from __future__ import annotations


def resolve_device(preference: str = 'AUTO') -> dict:
    """Resolve AI compute device from AUTO/CPU/GPU preference."""
    pref = (preference or 'AUTO').upper()
    info = {
        'preference': pref,
        'device': 'cpu',
        'backend': 'CPU',
        'cuda_available': False,
        'device_name': 'CPU',
        'vram_mb': 0,
        'status': 'Ready',
    }
    try:
        import torch
        info['cuda_available'] = bool(torch.cuda.is_available())
        if info['cuda_available']:
            info['device_name'] = torch.cuda.get_device_name(0)
            try:
                props = torch.cuda.get_device_properties(0)
                info['vram_mb'] = int(getattr(props, 'total_memory', 0) / (1024 * 1024))
            except Exception:
                pass
    except Exception:
        pass

    if pref == 'CPU':
        info['device'] = 'cpu'
        info['backend'] = 'CPU'
    elif pref == 'GPU':
        if info['cuda_available']:
            info['device'] = 'cuda'
            info['backend'] = 'CUDA'
        else:
            info['device'] = 'cpu'
            info['backend'] = 'CPU'
            info['status'] = 'GPU unavailable — using CPU'
    else:
        if info['cuda_available']:
            info['device'] = 'cuda'
            info['backend'] = 'CUDA'
        else:
            info['device'] = 'cpu'
            info['backend'] = 'CPU'
    return info

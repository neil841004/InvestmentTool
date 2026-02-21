import matplotlib.pyplot as plt
import io
import base64
import numpy as np

def create_sparkline(data, color='blue'):
    """
    Generates a sparkline image from data.
    Returns: base64 encoded image string.
    """
    if not data or len(data) < 2:
        return None
        
    # Setup plot without axes/margins
    fig, ax = plt.subplots(figsize=(2, 0.5))
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    
    # Normalize color (matplotlib name or hex)
    ax.plot(data, color=color, linewidth=2)
    ax.fill_between(range(len(data)), data, min(data), color=color, alpha=0.1)
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=100)
    plt.close(fig)
    
    # Encode
    data_uri = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{data_uri}"

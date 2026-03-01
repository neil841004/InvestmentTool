def create_sparkline(data, color='blue', width=200, height=50):
    """
    Generates a sparkline as an inline SVG string (no matplotlib overhead).
    Returns: SVG markup string for use with st.markdown(unsafe_allow_html=True).
    """
    if not data or len(data) < 2:
        return None

    n = len(data)
    min_val = min(data)
    max_val = max(data)
    val_range = max_val - min_val if max_val != min_val else 1

    # Build SVG polyline points
    points = []
    for i, v in enumerate(data):
        x = (i / (n - 1)) * width
        y = height - ((v - min_val) / val_range) * height
        points.append(f"{x:.1f},{y:.1f}")
    points_str = " ".join(points)

    # Build fill polygon (close path along bottom)
    fill_points = points_str + f" {width:.1f},{height} 0,{height}"

    svg = (
        f'<svg width="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;">'
        f'<polyline points="{fill_points}" fill="{color}" fill-opacity="0.1" stroke="none"/>'
        f'<polyline points="{points_str}" fill="none" stroke="{color}" stroke-width="2" '
        f'vector-effect="non-scaling-stroke"/>'
        f'</svg>'
    )
    return svg

# src\gui_common\styles\dark_theme.py
from __future__ import annotations


DARK_THEME_COLORS: dict[str, str] = {
    "bg": "#1e1f29",
    "bg_alt": "#252731",
    "panel": "#2a2c39",
    "panel_alt": "#30323f",
    "border": "#3a3d4d",
    "border_strong": "#4a4d5e",
    "text": "#e0e3eb",
    "text_muted": "#9aa0b4",
    "text_dim": "#6b7088",
    "accent": "#4a90e2",
    "accent_pressed": "#3978c1",
    "warning": "#f0a050",
    "success": "#4caf50",
    "danger": "#ef4f4f",
    "selection_bg": "#3b5374",
    "selection_text": "#ffffff",
    "header_bg": "#2f3242",
}


def style_matplotlib_figure(figure, *, axes=None) -> None:
    """Apply dark theme colors to a matplotlib Figure (and optional axes list).

    Call this each time before drawing if the figure is cleared, since
    matplotlib resets axis-level colors on clear().
    """
    c = DARK_THEME_COLORS
    figure.patch.set_facecolor(c["panel"])
    target_axes = axes if axes is not None else figure.get_axes()
    for ax in target_axes:
        ax.set_facecolor(c["bg_alt"])
        for spine in ax.spines.values():
            spine.set_edgecolor(c["border_strong"])
        ax.tick_params(colors=c["text_muted"], which="both")
        ax.xaxis.label.set_color(c["text"])
        ax.yaxis.label.set_color(c["text"])
        ax.title.set_color(c["text"])
        ax.grid(True, color=c["border"], linewidth=0.4, alpha=0.6)

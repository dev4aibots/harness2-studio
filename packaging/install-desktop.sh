#!/bin/sh
# Install Harness² Studio as a desktop app for the current user.
#
# Creates:
#   ~/.local/share/applications/harness2-studio.desktop   (app grid / search)
#   <Desktop>/harness2-studio.desktop                     (double-click icon)
#   ~/.local/share/icons/hicolor/{128,256,512}x*/apps/harness2-studio.png
#
# The launcher runs the app with a Python that already has Tk. When an installed
# `harness2-studio` command exists it is preferred; otherwise the script finds a
# Tk-capable interpreter. Override explicitly with HARNESS2_STUDIO_PYTHON.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$here/.." && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}
desktop_dir=$(xdg-user-dir DESKTOP 2>/dev/null || true)
[ -n "$desktop_dir" ] || desktop_dir="$HOME/Desktop"

pick_interpreter() {
    for candidate in ${HARNESS2_STUDIO_PYTHON:-} python3.12 python3.13 python3.11 python3; do
        [ -n "$candidate" ] || continue
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import tkinter' 2>/dev/null; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

if command -v harness2-studio >/dev/null 2>&1; then
    exec_line="harness2-studio"
else
    python=$(pick_interpreter) || {
        echo "No Tk-capable Python found. Install python3-tk or set HARNESS2_STUDIO_PYTHON." >&2
        exit 1
    }
    exec_line="\"$python\" \"$repo/run.py\""
fi

# -- icons ---------------------------------------------------------------
icon_name=harness2-studio
icon_ref=$icon_name
icons_root="$data/icons/hicolor"
if command -v magick >/dev/null 2>&1; then convert_cmd=magick
elif command -v convert >/dev/null 2>&1; then convert_cmd=convert
else convert_cmd=""
fi
if [ -n "$convert_cmd" ] && [ -f "$repo/h2studio/assets/icon.svg" ]; then
    for size in 128 256 512; do
        mkdir -p "$icons_root/${size}x${size}/apps"
        "$convert_cmd" "$repo/h2studio/assets/icon.svg" -background none -resize "${size}x${size}" \
            "$icons_root/${size}x${size}/apps/$icon_name.png" 2>/dev/null || true
    done
    if [ ! -f "$icons_root/256x256/apps/$icon_name.png" ]; then
        icon_ref="$repo/h2studio/assets/icon.png"
    fi
else
    icon_ref="$repo/h2studio/assets/icon.png"
fi
if [ -f "$repo/h2studio/assets/icon.svg" ]; then
    mkdir -p "$icons_root/scalable/apps"
    cp "$repo/h2studio/assets/icon.svg" "$icons_root/scalable/apps/$icon_name.svg"
fi

# -- desktop entries -----------------------------------------------------
mkdir -p "$data/applications"
applications_entry="$data/applications/$icon_name.desktop"
cat > "$applications_entry" <<EOF
[Desktop Entry]
Version=1.1
Type=Application
Name=Harness² Studio
GenericName=Agent Harness Control Room
Comment=Install, run, judge and inspect Google Research Harness²
Exec=$exec_line
Path=$repo
Icon=$icon_ref
Terminal=false
Categories=Development;IDE;
Keywords=harness;agent;google;research;benchmark;
StartupWMClass=harness2-studio
EOF

mkdir -p "$desktop_dir"
desktop_entry="$desktop_dir/$icon_name.desktop"
cp "$applications_entry" "$desktop_entry"
chmod +x "$applications_entry" "$desktop_entry"
# GNOME requires the launcher to be explicitly trusted before it will run.
if command -v gio >/dev/null 2>&1; then
    gio set "$desktop_entry" metadata::trusted true 2>/dev/null || true
    gio set "$applications_entry" metadata::trusted true 2>/dev/null || true
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$data/applications" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f -t "$icons_root" >/dev/null 2>&1 || true

echo "Installed Harness² Studio launcher:"
echo "  desktop icon : $desktop_entry"
echo "  app grid     : $applications_entry"
echo "  command      : $exec_line"
echo "  icon         : $icon_ref"

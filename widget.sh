#!/data/data/com.termux/files/usr/bin/bash
# wade_widget.sh
# Copy (don't symlink) this into ~/.shortcuts/ so Termux:Widget shows a
# "wade" icon you can add to your Android home screen — tapping it launches
# Wade the same way running wade_start.sh in Termux does.
#
# Setup (once):
#   1. Install the "Termux:Widget" app (same source as Termux — F-Droid).
#   2. mkdir -p ~/.shortcuts
#   3. cp wade_widget.sh ~/.shortcuts/wade.sh
#   4. Edit WADE_DIR below to wherever you put Wade's files in Termux.
#   5. chmod +x ~/.shortcuts/wade.sh
#   6. Long-press your Android home screen -> Widgets -> Termux:Widget ->
#      place it -> tap "wade".

WADE_DIR="$HOME/wade"

cd "$WADE_DIR" || {
    echo "Couldn't find $WADE_DIR — edit WADE_DIR at the top of this script."
    read -p "Press enter to close..."
    exit 1
}
termux-wake-lock 2>/dev/null  # keeps Termux from being killed while Wade runs, if installed
./wade_start.sh
termux-wake-unlock 2>/dev/null

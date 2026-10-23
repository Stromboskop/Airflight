# Eyes

Temporary face-animation tests for the Airflight Pico 2 W and its 320x240 ILI9341 display.

## Run from a PC over USB

The test runs from the PC in the Pico's RAM. It does not copy or replace the
Airflight `main.py` stored on the Pico.

1. Connect the Pico by USB and close Thonny or any other program using its
   serial port.
2. From this folder, run:

   ```powershell
   python -m mpremote connect COM4 run --no-follow eyes_test.py
   ```

   To run the nine-expression mood carousel instead, use:

   ```powershell
   python -m mpremote connect COM4 run --no-follow moods_test.py
   ```

3. The command returns while the animation continues on the Pico. Restart the
   Pico to stop the test and start its normal Airflight `main.py`.

The script uses the `ili9341.py` driver at the root of this repository, which
is already installed on the Pico by the Airflight project. The display wiring
is documented in [BRANCHEMENTS.md](../BRANCHEMENTS.md).

`moods_test.py` cycles through happy, sad, surprised, thoughtful, winking,
loving, angry, kissing, and dizzy expressions. The automatic carousel is a
prototype; it can later be replaced by event-triggered expression changes.

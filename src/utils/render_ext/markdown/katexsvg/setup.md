# Setup

Except for `pip` dependencies, the following steps are required.

```bash
# Install librsvg2-bin to convert svg to png
sudo apt install librsvg2-bin

# Install fonts
mkdir -p ~/.local/share/fonts
cp katexsvg/svgmath/fonts/files/* ~/.local/share/fonts
```
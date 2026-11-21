```
You are given two reference images:
1. art_style.png — MASTER character design sheet.
   Match ALL details exactly: color palette, outline thickness,
   body proportions, expression style.
2. grid_layout.png — layout reference for dimensions, cell sizes,
   green background (#00CC00), and grid line style only.

CRITICAL LAYOUT RULES:
- Replicate grid_layout.png EXACTLY: same dimensions, same green (#00CC00) background,
  same black grid lines, same cell sizes, 8 columns x 8 rows
- ALL columns must be IDENTICAL width — do NOT vary column width based on content
- ALL rows must be IDENTICAL height — do NOT vary row height based on content
- Grid must be perfectly uniform: a ruler placed on any column line must be perfectly straight
- Sprites scale to fit inside cell — cell size never changes to fit the sprite
- Replace ALL existing cell labels with the new names listed below
- Sprites must fit INSIDE their cell without overflowing into adjacent cells
- Do NOT add borders, watermarks, or decorations outside the grid
- Fill cells IN ORDER left to right, top to bottom — no gaps, no skipping

IMPORTANT — NO FINGER IN CAT SPRITES:
Do NOT include the finger/fingertip shape in any cat sprite cells.
Cat must act as if the finger is there on her right side, but the finger itself
must NOT appear in the sprite. Leave empty green space to the right where the finger would be.

IMPORTANT — CAT DIRECTION:
The finger marker is always positioned to the RIGHT of the cat.
ALL actions (wiping, spraying, inspecting) must be directed TOWARD the right side
where the finger marker is. The cat is always acting ON the marker/finger area,
NOT on herself. Cat body should lean or extend arms toward the right in all action frames.

Label and fill the first 24 cells as follows.
Label remaining 40 cells "reserve" and leave them empty green.

[finger_marker]
Simple rounded oval/fingertip shape, thick black outline,
soft peach/skin tone fill. Clean and minimal — represents a fingertip. No cat.

[arrow]
Curved hand-drawn arrow pointing toward the finger marker.
Thick black outline, white/cream fill, kawaii slightly wobbly style.

[noticing_a]
Dimsum Cat — just noticed the finger, leaning forward curious toward the right.
Eyes wide, one paw raised slightly, head tilted toward marker direction.

[noticing_b]
Dimsum Cat — disgusted/shocked expression looking at the finger (to the right).
One paw covering nose, other paw pointing at marker, eyebrows furrowed.
Expression: "eww this finger is dirty!"

[wiping_a]
Dimsum Cat — holding a tiny cloth with both paws, beginning to wipe.
Body leaning RIGHT toward the marker. Arms extended to the right.
Focused serious expression, ready to clean.

[wiping_b]
Dimsum Cat — actively wiping LEFT stroke toward the marker area on the right.
Arms extended right, cloth pressed against marker direction.
Focused squinted eyes, determined expression. Motion lines on cloth.

[wiping_c]
Dimsum Cat — wiping RIGHT stroke, opposite direction, still toward marker.
Arms still extended to the right, motion lines on cloth going other way.
Same focused serious expression.

[wiping_d]
Dimsum Cat — finishing wipe, pulling cloth back slightly, inspecting the marker area.
Leaning right to look, one eye squinted inspecting, cloth still in paw.
Almost satisfied expression.

[spraying_a]
Dimsum Cat — holding a tiny spray bottle in one paw, aiming nozzle to the RIGHT
toward the marker. Other paw steadying the bottle. Focused aim expression.

[spraying_b]
Dimsum Cat — pressing the nozzle, spraying toward the right/marker direction.
Small spray mist cloud coming out toward the right. Cheek puffed slightly.

[spraying_c]
Dimsum Cat — spray cloud visible to the right, cat squinting eyes from the mist.
One paw covering own nose/mouth, still holding bottle aimed right.

[spraying_d]
Dimsum Cat — fanning the sprayed area to the right with one paw.
Other paw still holding bottle. Eyes open, satisfied expression.

[inspect_a]
Dimsum Cat — leaning far to the RIGHT, face close to the marker area inspecting.
One paw on the ground for balance, other paw pointing at marker.
Very focused/critical inspection expression.

[inspect_b]
Dimsum Cat — holding a tiny magnifying glass, examining the marker area to the right.
Eye enlarged through magnifying glass. Very serious detective expression.

[inspect_c]
Dimsum Cat — standing back upright, looking right at marker area, nodding approvingly.
Paw on chin, satisfied smile. "Yes, this is clean now" expression.

[inspect_d]
Dimsum Cat — both paws raised in celebration, looking right at marker.
Big happy smile, sparkles around. "All clean!" expression.

[ending_a]
Dimsum Cat — looking at camera (forward), one eye winking, one paw thumbs up.
Proud and playful expression, sparkles around.

[ending_b]
Dimsum Cat — polite Korean service bow toward camera, eyes closed.
Paws together in front, slight smile, professional and cute.

[tiny_cloth]
Tiny cute cleaning cloth/towel prop, no cat. White with small pattern.
Folded neatly, kawaii style matching art_style.png props.

[spray_bottle]
Tiny cute spray bottle prop, no cat. Pastel blue or pink color.
Small sparkle on bottle, kawaii style matching art_style.png props.

[sparkle_a]
3-4 four-pointed stars, yellow and pink, small dots around. No cat.

[sparkle_b]
Same stars slightly rotated and resized for animation. No cat.

[heart]
2-3 small floating hearts, pink and red, kawaii thick outline. No cat.

[speech_bubble]
Round white speech bubble, thick black outline, completely empty inside.
Small tail at bottom left. Match prop style from art_style.png.
```

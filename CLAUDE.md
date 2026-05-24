# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Browser-based games built entirely in vanilla HTML5 Canvas with no dependencies, build steps, or bundlers. Each game is a self-contained single HTML file — open it directly in any browser to run it.

- `shooter.html` — SURVIVOR: top-down wave shooter
- `tictactoe.html` — Tic Tac Toe: 2-player and vs-AI

## Running the games

```bash
# Windows — open in default browser
start shooter.html
start tictactoe.html
```

No server required. No install step. No compilation.

## Git workflow

Every meaningful change should be committed and pushed. The remote is `https://github.com/jmansour77/browser-games` (branch `main`). Credentials are stored in Windows Credential Manager — `git push` works without re-authentication.

```bash
git add shooter.html          # or tictactoe.html
git commit -m "feat: ..."
git push
```

## shooter.html architecture

The entire game lives in one `<script>` block. Execution order within the file:

1. **Constants & config** — canvas dimensions (`W=800, H=600`), timing (`FIXED=1/60` fixed timestep), `EDEFS` (enemy stat table), `LEVELS` (wave definitions)
2. **Utility functions** — `clamp`, `circleHit` (squared-distance circle overlap, no sqrt), `randomEdge` (spawn positions off-screen)
3. **Classes** (in dependency order):
   - `Player` — movement (arrow/WASD), 4-frame walk animation via `LEGS` offset table, gun angle tracks mouse, `gunTip()` returns muzzle position
   - `Enemy` — type-driven rendering (grunt/runner/tank shapes), staggered `delay` before activating, white `flash` on hit
   - `BulletMgr` — flat object array, iterates backwards to splice safely, calls `onKill(pts)` callback when an enemy dies
   - `ParticleMgr` — `burst()` for death explosions, `muzzle()` for shot feedback, particles are plain objects not class instances
   - `Game` — owns all state; drives the loop, input, and state machine
4. **`new Game()`** — boots everything

### Game loop

Fixed-timestep accumulator pattern: `update(FIXED)` may run 0–N times per animation frame; `draw()` runs exactly once per frame. The 100ms dt cap prevents spiral-of-death on tab-switch.

### State machine

`STATE = { MENU, PLAY, WAVE_END, LVL_END, OVER }`

- `MENU` → click → `PLAY` (via `startGame()`)
- `PLAY` → all enemies dead, more waves → `WAVE_END` (2.2s auto-advance)
- `PLAY` → all enemies dead, last wave → `LVL_END` (click to continue, +30 HP)
- `PLAY` → player hp ≤ 0 → `OVER`
- `LVL_END` → click → `PLAY` (increments `this.li`, resets `this.wi`)
- `WAVE_END` → timer → `PLAY` (increments `this.wi`, calls `spawnWave()`)
- `OVER` → click → `MENU`

### Difficulty scaling

`spawnWave()` passes `mult = 1 + li * 0.18` to `new Enemy()`. HP scales linearly by `mult`; speed scales as `base * (1 + (mult-1)*0.5)` (half-rate to keep game playable).

### Rendering pipeline (each frame)

Background fill → floor grid → enemies → player → bullets → particles → HUD → state overlay

All art uses only `fillRect`, `arc`, `ellipse`, and `ctx.save/restore` with `translate/rotate`. No images or external assets.

### Adding a new enemy type

1. Add an entry to `EDEFS` with `{ hp, speed, r, color, dark, dmg, pts, type }`
2. Add a drawing branch in `Enemy.draw()` keyed on `this.type`
3. Reference the new key in any `LEVELS` wave object

### Adding a new level

Append to the `LEVELS` array. Each level is `{ name: string, waves: Array<{grunt?:n, runner?:n, tank?:n}> }`. Level count is not hardcoded anywhere — `endWave()` compares against `LEVELS.length`.

## tictactoe.html architecture

DOM-based (no Canvas). Game state is three module-level variables: `board` (9-element array), `current` ('X'|'O'), `gameOver`. The AI in `bestMove()` uses a simple priority: win → block → center → corner → random — not minimax.

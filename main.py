import math, random
from pygame import Rect
from pgzero.loaders import images, sounds
from pgzero import music

TITLE = "Milo the Mushroom - Lite"
WIDTH, HEIGHT = 960, 540

#constantes de física para fácil manutenção
gravity = 1800.0
move_acceleration = 2400.0
move_motion = 2200.0
max_speed = 260.0
jump_speed = 640.0
ground_y = HEIGHT - 60

#intervalo nos sons de passos dos personagens
step_interval_player = 0.38
step_interval_skeleton = 0.48

class Assets:
    #centralização de funções de carregamento e seleção de sprites de player e inimigos
    def sequence_loader(prefix):  
        frames, i = [], 0
        while True:
            name = f"{prefix}_{i}"
            try:
                images.load(name)
                frames.append(name)
                i += 1
            except Exception:
                break
        if not frames:
            try:
                images.load(prefix)
                frames.append(prefix)
            except Exception:
                pass
        return frames
    #dicionário para animações do inimigo, incluindo variações para esquerda
    def enemy_frames(prefix):
        names = ("idle", "walk", "hurt", "die", "attack")
        data = {name: Assets.sequence_loader(f"{prefix}_{name}") for name in names}
        #filtro para incluir variações para esquerda
        data.update({f"{name}_left": frames for name in names if (frames := Assets.sequence_loader(f"{prefix}_{name}_left"))})
        return data
    #filtro para sequencia de frames correta do player, incluindo variações para esquerda
    def player_frames(anim, facing):
        if facing > 0:
            return Assets.playerleft.get(f"{anim}_left", Assets.player.get(anim, []))
        return Assets.player.get(anim, [])
    #filtro para retornar sequencia de frames correta do inimigo, incluindo variações para esquerda
    def enemy_frames_logic(kind, anim, facing):
        framelogic = Assets.enemies.get(kind, Assets.enemies["skeleton"])
        key = f"{anim}_left" if facing < 0 else anim
        frames = framelogic.get(key, [])
        return frames or framelogic.get(anim, [])
playernames = ("idle", "run", "hit", "die", "attack") 
Assets.player = {name: Assets.sequence_loader(f"milo_{name}") for name in playernames}
Assets.playerleft = {f"{name}_left": Assets.sequence_loader(f"milo_{name}_left") for name in playernames}
Assets.enemies = {kind: Assets.enemy_frames(prefix) for kind, prefix in {"skeleton": "skeleton", "skeleton_yellow": "skeleton_y"}.items()}

def clamp(value, low, high):
    return max(low, min(high, value))
#"Centralizador" de entidades para evitar saída da tela
def clamp_entity(entity):
    entity.x = clamp(entity.x, 0.0, WIDTH - entity.w); entity.y = clamp(entity.y, 0.0, ground_y - entity.h)
def rect_of(entity):
    return Rect(int(entity.x), int(entity.y), int(entity.w), int(entity.h))

#Track de música
TRACK = "music"
#Nomes dos sons
SOUND_NAMES = ["menu_select", "music", "skeleton_attack", "skeleton_die", "skeleton_hurt",
               "skeleton_steps", "milo_attack", "milo_hurt", "milo_steps", "milo_jump",
               "raid_advance", "attack", "hit", "jump", "death"]
#Variáveis globais para controlar áudio
audio_on = True #switch global de áudio
_audio_channel = None #canal alternativo, em caso de falha do PgZero
#lógica de switch de áudio para "ligar" e "desligar" áudio
def audio_volume():
    return 1.0 if audio_on else 0.0
#Aplica volume a música e sons, ou não, caso áudio esteja off
def apply_audio():
    vol = 1.0 if audio_on else 0.0
    music.set_volume(vol)
    for name in SOUND_NAMES:
        clip = getattr(sounds, name, None)
        if clip:
            clip.set_volume(vol)
    if not audio_on:
        music.pause()
#Garantia caso o pgzero.music falhe, nesse caso, ele tocará pelo mixer de "sounds". Tive alguns problemas iniciais para tocar a música de fundo.
def check_music():
    global _audio_channel
    if not audio_on:
        return
    vol = audio_volume()
    try:
        music.play(TRACK); music.set_volume(vol); _audio_channel = None; return
    except Exception:
        pass
    if _audio_channel:
        try:
            if _audio_channel.get_busy():
                _audio_channel.set_volume(vol)
                return
        except Exception:
            _audio_channel = None
    if not sounds:
        return
    try:
        loop = getattr(sounds, TRACK); _audio_channel = loop.play(-1)
        if _audio_channel: _audio_channel.set_volume(vol)
    except Exception:
        _audio_channel = None
#Toca SFX por nome, respeitando variáveis de volume global, para evitar quebra.
def play_sound(name):
    if not sounds:
        return
    try:
        clip = getattr(sounds, name)
        clip.set_volume(audio_volume())
        clip.play()
    except Exception: pass
#Switch de som, lógica de double check de som aqui
def toggle_audio():
    global audio_on
    audio_on = not audio_on; apply_audio()
    if audio_on: check_music()
#Definições de animações de sprites gerais
class AnimatedEntity:
    def __init__(self, WIDTH, HEIGHT):
        self.w, self.h = WIDTH, HEIGHT
        self.anim = "idle"
        self.anim_index = 0
        self.anim_timer = 0.0
        self.anim_fps = 10.0
        self.facing = 1
        self.actor = Actor("logo")
    def frames(self):
        return []
    def image(self):
        frames = self.frames()
        if not frames:
            return "logo"
        idx = max(0, min(len(frames) - 1, self.anim_index))
        return frames[idx]
    def set_anim(self, name, fps):
        if name != self.anim:
            self.anim = name
            self.anim_index = 0
            self.anim_timer = 0.0
        if fps is not None:
            self.anim_fps = fps
    def advance_anim(self, dt):
        frames = self.frames()
        if not frames:
            return
        self.anim_timer += dt
        step = 1.0 / max(1e-6, self.anim_fps)
        while self.anim_timer >= step:
            self.anim_timer -= step
            if self.anim == "die":
                self.anim_index = min(len(frames) - 1, self.anim_index + 1)
            else:
                self.anim_index = (self.anim_index + 1) % len(frames)
    def draw(self):
        self.actor.image = self.image()
        try:
            self.actor.topleft = (int(self.x), int(self.y))
        except Exception:
            self.actor.pos = (int(self.x) + self.w // 2, int(self.y) + self.h // 2)
        self.actor.draw()
#Classe do "player", toda movimentação e funções do personsagem principal (Milo) aqui
class Player(AnimatedEntity):
    def __init__(self):
        super().__init__(36, 48)
        self.max_hp = 3
        self.actor = Actor("milo_idle_0")
        self.reset()    
    def frames(self):
        return Assets.player_frames(self.anim, self.facing)
    def reset(self):
        self.x, self.y, self.vx, self.vy = 160.0, ground_y - 40.0, 0.0, 0.0
        self.on_ground, self.facing, self.hp = True, 1, self.max_hp
        self.attack_time, self.cool_left, self.attack_len, self.cooldown = 0.0, 0.0, 0.15, 0.3
        self.step_timer = step_interval_player
        self.set_anim("idle", 10.0)
    def update(self, dt, keyboard):
        if self.cool_left > 0: self.cool_left = max(0.0, self.cool_left - dt)
        if self.attack_time > 0: self.attack_time = max(0.0, self.attack_time - dt)
        move = (1 if keyboard.right else 0) - (1 if keyboard.left else 0)
        if move:
            self.facing = 1 if move > 0 else -1
            self.vx = clamp(self.vx + move_acceleration * move * dt, -max_speed, max_speed)
        else:
            friction = move_motion * dt
            if abs(self.vx) <= friction:
                self.vx = 0.0
            else:
                self.vx -= friction * math.copysign(1, self.vx)
        attacking = self.attack_time > 0
        if self.hp > 0 and not attacking:
            running = abs(self.vx) > 1
            self.set_anim("run" if running else "idle", 12.0 if running else 6.0)
        elif attacking:
            self.set_anim("attack", 15.0)
        moving = self.on_ground and abs(self.vx) > 20 and not attacking and self.hp > 0
        if moving:
            self.step_timer -= dt
            if self.step_timer <= 0:
                play_sound("milo_steps")
                self.step_timer = max(0.22, step_interval_player - abs(self.vx) * 0.0012)
        else:
            self.step_timer = step_interval_player
        if keyboard.x and self.on_ground:
            self.vy = -jump_speed; self.on_ground = False; play_sound("milo_jump")
        self.vy += gravity * dt; self.x += self.vx * dt; self.y += self.vy * dt; clamp_entity(self)
        if self.y + self.h >= ground_y:
            self.y = ground_y - self.h; self.vy = 0.0; self.on_ground = True
        if keyboard.z and self.cool_left == 0 and not attacking:
            self.attack_time = self.attack_len; self.cool_left = self.cooldown; play_sound("milo_attack")
        self.advance_anim(dt)
    def attack_rect(self):
        if self.attack_time <= 0: return None
        reach = 28; x = self.x + (self.w // 2) + self.facing * 12
        if self.facing < 0: x -= reach
        return Rect(int(x), int(self.y) + 10, reach, self.h - 20)
    def take_hit(self, damage):
        self.vx = -self.facing * 240
        self.vy = -320
        self.on_ground = False
        if self.hp > 0:
            self.hp = max(0, self.hp - damage)
            play_sound("milo_hurt")
        if self.hp <= 0:
            self.set_anim("die", 8.0)
            play_sound("death")
            return True
        return False
#Gerenciamento dos inimigos skeleton e skeleton_yellow. Não tive tempo de colocar mais :(
class Enemy(AnimatedEntity):
    types = {
        "skeleton": {"hp": 1, "speed": 100, "damage": 1, "range": 36, "chase": 200, "attack_len": 0.6,
                     "w": 34, "h": 42, "walk_fps": 8.0, "pause": None, "idle_fps": 6.0, "walk_pause": None},
        "skeleton_yellow": {"hp": 2, "speed": 120, "damage": 1, "range": 40, "chase": 220, "attack_len": 0.5,
                            "w": 36, "h": 44, "walk_fps": 10.0, "pause": (1.0, 3.0), "idle_fps": 6.0, "walk_pause": (2.0, 4.0)},
    }
    step_types = {"skeleton", "skeleton_yellow"}
    def __init__(self, kind, raid_level):
        kind = kind if kind in self.types else "skeleton"
        stats = self.types[kind]
        super().__init__(stats["w"], stats["h"])
        self.kind = kind
        raid_index = max(0, raid_level - 1)
        hp_scale, speed_scale = 1.0 + raid_index * 0.45, 1.0 + raid_index * 0.15
        self.max_hp = max(1, int(math.ceil(stats["hp"] * hp_scale)))
        self.current_hp = self.max_hp
        self.speed = max(10, int(math.ceil(stats["speed"] * speed_scale)))
        base_damage = stats["damage"]
        if raid_level >= 5:
            dmg_scale = 1.0 + (raid_level - 5) * 0.15
            base_damage = max(base_damage + (raid_level - 4) // 2, int(math.ceil(base_damage * dmg_scale)))
        self.damage = base_damage
        self.attack_range, self.chase_range, self.attack_len = stats["range"], stats["chase"], stats["attack_len"]
        self.dir = random.choice([-1, 1])
        self.x, self.y = random.randint(360, WIDTH - 80), ground_y - self.h
        self.state, self.attack_time, self.die_timer = "patrol", 0.0, 0.0
        self.is_paused, self.patrol_timer = False, 0.0
        self.pause_range, self.walk_pause_range = stats["pause"], stats["walk_pause"]
        self.patrol_pause = random.uniform(*self.pause_range) if self.pause_range else 0.0
        self.walk_pause = random.uniform(*self.walk_pause_range) if self.walk_pause_range else 0.0
        self.walk_fps, self.idle_fps = stats["walk_fps"], stats["idle_fps"]
        self.step_timer = random.uniform(0.1, 0.35)
        self.remove = False
        self.actor = Actor(self.image())
        clamp_entity(self)
    def frames(self):
        return Assets.enemy_frames_logic(self.kind, self.anim, self.facing)
    def update_steps(self, dt, moving):
        if self.kind not in self.step_types:
            return
        if moving:
            self.step_timer -= dt
            if self.step_timer <= 0:
                play_sound("skeleton_steps")
                self.step_timer = max(0.18, step_interval_skeleton - self.speed * 0.0012)
        else:
            self.step_timer = min(self.step_timer, 0.18)
    def rect(self):
        return rect_of(self)
    def take_hit(self):
        if self.state == "die" or self.remove:
            return "ignore"
        self.current_hp -= 1
        if self.current_hp <= 0:
            self.state = "die"; self.die_timer = 1.5; self.set_anim("die", 10.0); return "die"
        self.set_anim("hurt", 12.0); return "hurt"
    def update(self, dt, player):
        if self.state == "die":
            self.die_timer = max(0.0, self.die_timer - dt)
            if self.die_timer == 0.0: self.remove = True
            self.advance_anim(dt); return
        if self.attack_time > 0:
            self.attack_time = max(0.0, self.attack_time - dt)
        ex_center = self.x + self.w * 0.5
        pl_center = player.x + player.w * 0.5
        dx, dist = pl_center - ex_center, abs(pl_center - ex_center)
        self.state = "attack" if self.attack_time > 0 or dist <= self.attack_range else ("chase" if dist <= self.chase_range else "patrol")
        if self.state == "patrol":
            if self.pause_range:
                self.patrol_timer += dt
                if self.is_paused:
                    if self.patrol_timer >= self.patrol_pause:
                        self.is_paused = False; self.patrol_timer = 0.0
                        self.patrol_pause = random.uniform(*self.pause_range); self.dir = random.choice([-1, 1])
                    self.set_anim("idle", self.idle_fps); self.update_steps(dt, False)
                else:
                    self.x += self.dir * self.speed * dt
                    if self.x <= 360 or self.x + self.w >= WIDTH - 40: self.dir *= -1
                    self.facing = -1 if self.dir < 0 else 1
                    self.set_anim("walk", self.walk_fps); self.update_steps(dt, True)
                    if self.patrol_timer >= self.walk_pause:
                        self.is_paused = True; self.patrol_timer = 0.0
                        self.walk_pause = random.uniform(*self.walk_pause_range)
            else:
                self.x += self.dir * self.speed * dt
                if self.x <= 360 or self.x + self.w >= WIDTH - 40: self.dir *= -1
                self.facing = -1 if self.dir < 0 else 1
                self.set_anim("walk", self.walk_fps); self.update_steps(dt, True)
        elif self.state == "chase":
            self.dir = -1 if dx < 0 else 1
            self.x += self.dir * (self.speed + 40) * dt
            self.facing = -1 if self.dir < 0 else 1
            self.set_anim("walk", 10.0); self.update_steps(dt, True)
        else:
            self.dir = -1 if dx < 0 else 1
            self.facing = -1 if self.dir < 0 else 1
            if self.attack_time == 0:
                self.attack_time = self.attack_len
                if self.kind in self.step_types:
                    play_sound("skeleton_attack")
            self.set_anim("attack", 12.0); self.update_steps(dt, False)
        clamp_entity(self); self.advance_anim(dt)
#Gerenciamento do jogo, estados, raids, score, entrada de mouse e teclado, atualização dos actors, background, UI e sprites.
class Game:
    def __init__(self):
        self.state = "menu"
        self.score = 0
        self.current_raid = 1
        self.enemies_spawned = 0
        self.player = Player()
        self.enemies: list[Enemy] = []
        self.start_btn = Rect((WIDTH / 2 - 120, HEIGHT / 2 + 50), (240, 50))
        self.sound_btn = Rect((WIDTH / 2 - 120, HEIGHT / 2 + 120), (240, 50))
        self.exit_btn = Rect((WIDTH / 2 - 120, HEIGHT / 2 + 190), (240, 50))
    def reset(self):
        self.player.reset()
        self.score = 0
        self.current_raid = 1
        self.enemies_spawned = 0
        self.enemies = self.spawn_raid()
        self.state = "game"
    def spawn_raid(self):
        raid = self.current_raid
        count = 4 if raid == 1 else 4 + 2 ** (raid - 2)
        types = ["skeleton"] if raid == 1 else ["skeleton", "skeleton_yellow"]
        pack = [Enemy(random.choice(types), raid) for _ in range(count)]
        self.enemies_spawned += count
        return pack
    def advance_raid(self):
        play_sound("raid_advance")
        self.current_raid += 1
        if self.current_raid % 3 == 1 and self.current_raid > 1:
            self.player.hp = min(self.player.max_hp, self.player.hp + 1)
        self.enemies = self.spawn_raid()
    def update(self, dt):
        check_music()
        if self.state != "game":
            return
        self.player.update(dt, keyboard)
        attack_rect = self.player.attack_rect()
        player_rect = rect_of(self.player)
        for enemy in self.enemies:
            enemy.update(dt, self.player)
            if enemy.state == "attack" and enemy.attack_time > 0 and enemy.rect().colliderect(player_rect):
                if self.player.take_hit(enemy.damage):
                    self.state = "gameover"
            if attack_rect and enemy.state != "die" and not enemy.remove and enemy.rect().colliderect(attack_rect):
                result = enemy.take_hit()
                if result == "die":
                    self.score += 100
                    play_sound("skeleton_die" if enemy.kind in Enemy.step_types else "hit")
                elif result == "hurt":
                    play_sound("skeleton_hurt" if enemy.kind in Enemy.step_types else "hit")
        self.enemies = [e for e in self.enemies if not e.remove]
        if not self.enemies and self.state == "game":
            self.advance_raid()
    def draw(self):
        screen.fill((200, 228, 255))
        for name, pos in (("background", (0, 0)), ("ground", (0, ground_y))):
            try:
                screen.blit(name, pos)
            except Exception:
                if name == "ground":
                    screen.draw.filled_rect(Rect(0, ground_y, WIDTH, HEIGHT - ground_y), (154, 118, 84))
        if self.state == "menu":
            Actor("logo", (WIDTH / 2, HEIGHT / 2 - 120)).draw()
            for rect, label in ((self.start_btn, "START"), (self.sound_btn, f"SOUND: {'ON' if audio_on else 'OFF'}"), (self.exit_btn, "EXIT")):
                screen.draw.filled_rect(rect, (255, 255, 255)); screen.draw.text(label, center=rect.center, fontsize=32, color="black")
            return
        self.player.draw()
        for enemy in self.enemies:
            enemy.draw()
        for text, pos, size, color in (
            ("+ " * self.player.hp, (16, 12), 40, (230, 40, 60)),
            (f"SCORE: {self.score}", (16, 60), 32, (255, 255, 255)),
            (f"RAID: {self.current_raid}", (16, 100), 28, (255, 255, 0)),
        ):
            screen.draw.text(text, topleft=pos, fontsize=size, color=color)
        if self.state == "gameover":
            panel = Rect(WIDTH // 2 - 200, HEIGHT // 2 - 100, 400, 200)
            screen.draw.filled_rect(panel, (0, 0, 0, 180))
            for msg, offset, size, color, owidth in (
                ("GAME OVER", -60, 48, "red", 2),
                (f"FINAL SCORE: {self.score}", -20, 32, "yellow", 1),
                (f"RAID REACHED: {self.current_raid}", 10, 24, "white", 1),
                ("PRESS 'R' TO RESTART", 50, 28, "lime", 1),
            ):
                screen.draw.text(msg, center=(WIDTH // 2, HEIGHT // 2 + offset), fontsize=size, color=color, owidth=owidth)
        elif self.state == "win":
            screen.draw.text("YOU WIN! - CLICK TO RESTART", center=(WIDTH // 2, HEIGHT // 2),
                             fontsize=40, color="white", owidth=1)
    def on_mouse_down(self, pos):
        if self.state != "menu":
            return
        if self.start_btn.collidepoint(pos):
            self.reset()
            play_sound("menu_select")
        elif self.sound_btn.collidepoint(pos):
            toggle_audio()
            play_sound("menu_select")
        elif self.exit_btn.collidepoint(pos):
            raise SystemExit
    def on_key_down(self, key):
        if self.state == "gameover" and key == keys.R:
            self.reset()
            play_sound("menu_select")
    def on_start(self):
        apply_audio()
        check_music()
game = Game()
#Lógica padrão do PgZero
def update(dt):
    game.update(dt)
def draw():
    game.draw()
def on_mouse_down(pos):
    game.on_mouse_down(pos)
def on_key_down(key):
    game.on_key_down(key)
def on_start():
    game.on_start()


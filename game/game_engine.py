import pygame
from .player import Player
from .platform import Platform
from .hazard import Hazard
from .sounds import SoundManager

# Game Engine

WHITE = (255, 255, 255)
BROWN = (150, 100, 60)
RED = (220, 60, 60)
GREEN = (0, 200, 0)

# Difficulty presets: heavier gravity = shorter, snappier jumps (harder).
# Values were checked with a brute-force solver so every level is beatable.
DIFFICULTIES = {
    "Easy":   {"gravity": 0.4, "jump_strength": -13},
    "Medium": {"gravity": 0.6, "jump_strength": -12},
    "Hard":   {"gravity": 0.7, "jump_strength": -12},
}
DEFAULT_DIFFICULTY = "Medium"

# Game-over menu: number keys (main row and keypad) -> difficulty.
MENU_KEYS = {
    pygame.K_1: "Easy", pygame.K_KP1: "Easy",
    pygame.K_2: "Medium", pygame.K_KP2: "Medium",
    pygame.K_3: "Hard", pygame.K_KP3: "Hard",
}

# Fastest the player may fall, in pixels per frame. Kept well below
# (platform height + player height) so even a naive overlap check could not
# skip a platform; the swept check below makes landings reliable regardless.
MAX_FALL_SPEED = 18
# Float tolerance when asking "were the feet at/above the platform top?"
LANDING_EPSILON = 1

class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.start_x, self.start_y = 40, height - 120

        # A simple hand-built level: platforms with gaps between them
        # (falling into a gap means falling off the bottom of the
        # screen), one hazard, and a goal near the right edge.
        ground_y = height - 40
        self.platforms = [
            Platform(0, ground_y, 160),
            Platform(220, ground_y, 140),
            Platform(420, ground_y - 60, 120),
            Platform(600, ground_y, 180),
        ]
        self.hazards = [Hazard(240, ground_y - 14, 100)]
        self.goal_x = 740

        self.font = pygame.font.SysFont("Arial", 30)
        self.title_font = pygame.font.SysFont("Arial", 72, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 24)
        self.sounds = SoundManager()

        self.reset(DEFAULT_DIFFICULTY)

    def reset(self, difficulty):
        """Start a fresh run at the given difficulty ("Easy"/"Medium"/"Hard")."""
        settings = DIFFICULTIES[difficulty]
        self.difficulty = difficulty
        self.gravity = settings["gravity"]

        self.player = Player(self.start_x, self.start_y)
        self.player.jump_strength = settings["jump_strength"]

        self.score = 0
        self.game_over = False
        self.game_over_reason = ""

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.game_over:
            # Game-over menu: pick a difficulty to play again, or exit.
            if event.key in MENU_KEYS:
                self.reset(MENU_KEYS[event.key])
            elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            return

        if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            if self.player.jump():
                self.sounds.play("jump")

    def handle_input(self):
        keys = pygame.key.get_pressed()
        self.player.vx = 0
        if self.game_over:
            return
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player.vx = -self.player.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player.vx = self.player.speed

    def update(self):
        if self.game_over:
            return

        # Remember where the player's feet were BEFORE this frame's movement.
        # Comparing "was above the platform last frame" with "is at/below
        # its top now" catches landings even if the player moved further
        # than the platform is thick in a single frame (swept collision).
        prev_bottom = self.player.y + self.player.height

        # Terminal velocity: stops vertical speed growing without limit.
        self.player.vy = min(self.player.vy + self.gravity, MAX_FALL_SPEED)
        self.player.x = max(0, self.player.x + self.player.vx)
        self.player.y += self.player.vy

        self.player.on_ground = False
        self._land_on_platforms(prev_bottom)

        for hazard in self.hazards:
            if self.player.rect().colliderect(hazard.rect()):
                self._trigger_game_over("You touched a hazard!")
                return

        if self.player.y > self.height:
            self._trigger_game_over("You fell off the screen!")
            return

        if self.player.x >= self.goal_x:
            self.score += 1
            self.sounds.play("goal")
            self.player.x, self.player.y = self.start_x, self.start_y
            self.player.vy = 0

    def _trigger_game_over(self, reason):
        self.game_over = True
        self.game_over_reason = reason
        self.player.vx = 0
        self.sounds.play("death")

    def _land_on_platforms(self, prev_bottom):
        """Land the player on the highest platform whose top surface they
        crossed (or touched) while moving down this frame."""
        player = self.player
        if player.vy < 0:
            return  # moving up: platforms are one-way, jump through them

        new_bottom = player.y + player.height
        landing = None
        for platform in self.platforms:
            overlaps_horizontally = (
                player.x < platform.x + platform.width
                and player.x + player.width > platform.x
            )
            if not overlaps_horizontally:
                continue
            was_above = prev_bottom <= platform.y + LANDING_EPSILON
            reached_top = new_bottom >= platform.y
            if was_above and reached_top:
                # If several platforms were crossed, the highest one is hit first.
                if landing is None or platform.y < landing.y:
                    landing = platform

        if landing is not None:
            player.y = landing.y - player.height
            player.vy = 0
            player.on_ground = True

    def render(self, screen):
        for platform in self.platforms:
            pygame.draw.rect(screen, BROWN, platform.rect())
        for hazard in self.hazards:
            pygame.draw.rect(screen, RED, hazard.rect())

        goal_rect = pygame.Rect(self.goal_x, 0, 6, self.height)
        pygame.draw.rect(screen, GREEN, goal_rect)

        pygame.draw.rect(screen, WHITE, self.player.rect())

        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        screen.blit(score_text, (10, 10))
        diff_text = self.small_font.render(f"Difficulty: {self.difficulty}", True, WHITE)
        screen.blit(diff_text, diff_text.get_rect(topright=(self.width - 10, 14)))

        if self.game_over:
            self._render_game_over(screen)

    def _render_game_over(self, screen):
        # Dim the frozen scene so the message stands out.
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        cx = self.width // 2
        lines = [
            (self.title_font, "GAME OVER", RED, 90),
            (self.small_font, self.game_over_reason, WHITE, 150),
            (self.font, f"Final Score: {self.score}", WHITE, 195),
            (self.font, "Play again - choose a difficulty:", WHITE, 270),
            (self.small_font, "1 - Easy", GREEN, 315),
            (self.small_font, "2 - Medium", GREEN, 350),
            (self.small_font, "3 - Hard", GREEN, 385),
            (self.small_font, "ESC or Q - Exit", WHITE, 435),
        ]
        for font, text, color, y in lines:
            surf = font.render(text, True, color)
            screen.blit(surf, surf.get_rect(center=(cx, y)))

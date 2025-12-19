import pygame
import sys
import math
import numpy as np
from enum import Enum

# ----------------------------
# Settings
# ----------------------------
WIDTH, HEIGHT = 1200, 800
FPS = 60
BACKGROUND_COLOR = (25, 25, 40)
UI_BG_COLOR = (40, 40, 60)
ACCENT_COLOR = (0, 200, 255)
SECONDARY_COLOR = (255, 100, 100)
TEXT_COLOR = (240, 240, 255)
HIGHLIGHT_COLOR = (100, 255, 255)

# ----------------------------
# Real Hand Anatomy with Palm Facing Forward
# ----------------------------
class RealHand:
    def __init__(self, x, y, scale=1.0, is_right=True):
        self.x = x
        self.y = y
        self.scale = scale
        self.is_right = is_right
        
        # Real hand proportions based on human anatomy
        self.finger_data = {
            'thumb': {
                'base_angle': -20 if is_right else 20,
                'segments': [
                    {'length': 40, 'angle': 0},   # Metacarpal
                    {'length': 30, 'angle': 0},   # Proximal phalanx  
                    {'length': 25, 'angle': 0}    # Distal phalanx
                ]
            },
            'index': {
                'base_angle': 0,
                'segments': [
                    {'length': 45, 'angle': 0},   # Metacarpal
                    {'length': 35, 'angle': 0},   # Proximal phalanx
                    {'length': 25, 'angle': 0},   # Middle phalanx
                    {'length': 20, 'angle': 0}    # Distal phalanx
                ]
            },
            'middle': {
                'base_angle': 0,
                'segments': [
                    {'length': 50, 'angle': 0},   # Metacarpal
                    {'length': 40, 'angle': 0},   # Proximal phalanx
                    {'length': 30, 'angle': 0},   # Middle phalanx
                    {'length': 25, 'angle': 0}    # Distal phalanx
                ]
            },
            'ring': {
                'base_angle': 0,
                'segments': [
                    {'length': 45, 'angle': 0},   # Metacarpal
                    {'length': 35, 'angle': 0},   # Proximal phalanx
                    {'length': 25, 'angle': 0},   # Middle phalanx
                    {'length': 20, 'angle': 0}    # Distal phalanx
                ]
            },
            'pinky': {
                'base_angle': 0,
                'segments': [
                    {'length': 35, 'angle': 0},   # Metacarpal
                    {'length': 25, 'angle': 0},   # Proximal phalanx
                    {'length': 20, 'angle': 0},   # Middle phalanx
                    {'length': 15, 'angle': 0}    # Distal phalanx
                ]
            }
        }
        
        # Palm dimensions
        self.palm_width = 80
        self.palm_height = 100
        self.wrist_width = 50
        self.wrist_height = 30
        
        # Colors for realistic skin
        self.skin_base = (220, 180, 140)
        self.skin_shadow = (200, 160, 120)
        self.skin_highlight = (240, 200, 160)
        self.knuckle_color = (210, 170, 130)
        self.nail_color = (250, 230, 210)
        
        # Animation state
        self.target_pose = None
        self.current_pose = None
        self.animation_progress = 0
        self.animation_speed = 0.08
        
    def set_pose(self, pose_name):
        self.target_pose = pose_name
        self.animation_progress = 0
        self.current_pose = self.get_pose_data(pose_name)
        
    def get_pose_data(self, pose_name):
        # Real ASL poses with proper finger angles
        poses = {
            'rest': {
                'thumb': [10, 15, 5],
                'index': [0, 0, 0, 0],
                'middle': [0, 0, 0, 0],
                'ring': [0, 0, 0, 0],
                'pinky': [0, 0, 0, 0],
                'wrist_angle': 0
            },
            'hello': {
                'thumb': [0, 0, 0],
                'index': [0, -80, -80, -80],
                'middle': [0, -80, -80, -80],
                'ring': [0, -80, -80, -80],
                'pinky': [0, -80, -80, -80],
                'wrist_angle': 0
            },
            'thank_you': {
                'thumb': [0, 0, 0],
                'index': [0, 0, 0, 0],
                'middle': [0, 0, 0, 0],
                'ring': [0, 0, 0, 0],
                'pinky': [0, 0, 0, 0],
                'wrist_angle': 0
            },
            'i_love_you': {
                'thumb': [60, 30, 10],
                'index': [0, 0, 0, 0],
                'middle': [0, -80, -80, -80],
                'ring': [0, -80, -80, -80],
                'pinky': [0, 0, 0, 0],
                'wrist_angle': 5
            },
            'yes': {
                'thumb': [0, 0, 0],
                'index': [0, -10, -20, -10],
                'middle': [0, -10, -20, -10],
                'ring': [0, -10, -20, -10],
                'pinky': [0, -10, -20, -10],
                'wrist_angle': 0
            },
            'no': {
                'thumb': [0, 0, 0],
                'index': [0, -45, -90, -45],
                'middle': [0, -45, -90, -45],
                'ring': [0, -45, -90, -45],
                'pinky': [0, -45, -90, -45],
                'wrist_angle': 0
            }
        }
        return poses.get(pose_name, poses['rest'])
    
    def update(self):
        if self.target_pose and self.current_pose:
            self.animation_progress += self.animation_speed
            if self.animation_progress > 1:
                self.animation_progress = 1
    
    def draw(self, surface):
        # Draw wrist (horizontal oval)
        wrist_rect = pygame.Rect(0, 0, self.wrist_width * self.scale, self.wrist_height * self.scale)
        wrist_rect.center = (self.x, self.y)
        pygame.draw.ellipse(surface, self.skin_shadow, wrist_rect)
        
        # Draw palm (facing forward - vertical oval)
        palm_rect = pygame.Rect(0, 0, self.palm_width * self.scale, self.palm_height * self.scale)
        palm_rect.midtop = (self.x, self.y)
        
        # Palm with 3D effect
        self.draw_rounded_rect(surface, palm_rect, self.skin_base, 15)
        
        # Draw knuckles at finger bases
        knuckle_y = palm_rect.top + 20 * self.scale
        knuckle_spacing = 15 * self.scale
        knuckle_positions = [
            (self.x - knuckle_spacing * 2, knuckle_y),  # pinky
            (self.x - knuckle_spacing, knuckle_y),      # ring
            (self.x, knuckle_y),                        # middle
            (self.x + knuckle_spacing, knuckle_y),      # index
        ]
        
        for pos in knuckle_positions:
            pygame.draw.circle(surface, self.knuckle_color, pos, 8 * self.scale)
            pygame.draw.circle(surface, self.skin_highlight, 
                             (pos[0] - 2 * self.scale, pos[1] - 2 * self.scale), 
                             3 * self.scale)
        
        # Draw thumb base knuckle (special position)
        thumb_base_x = self.x - (self.palm_width * 0.3) * self.scale
        thumb_base_y = palm_rect.top + 60 * self.scale
        pygame.draw.circle(surface, self.knuckle_color, (thumb_base_x, thumb_base_y), 10 * self.scale)
        
        # Draw fingers
        self.draw_fingers(surface, palm_rect)
        
        # Draw palm creases for realism
        self.draw_palm_creases(surface, palm_rect)
    
    def draw_fingers(self, surface, palm_rect):
        finger_order = ['pinky', 'ring', 'middle', 'index', 'thumb']
        finger_colors = {
            'thumb': self.skin_shadow,
            'index': self.skin_base,
            'middle': self.skin_base,
            'ring': self.skin_base,
            'pinky': self.skin_shadow
        }
        
        # Finger base positions (palm facing forward)
        base_positions = {
            'pinky': (self.x - 30 * self.scale, palm_rect.top + 15 * self.scale),
            'ring': (self.x - 15 * self.scale, palm_rect.top + 10 * self.scale),
            'middle': (self.x, palm_rect.top + 8 * self.scale),
            'index': (self.x + 15 * self.scale, palm_rect.top + 10 * self.scale),
            'thumb': (self.x - 25 * self.scale, palm_rect.top + 60 * self.scale)
        }
        
        for finger_name in finger_order:
            base_pos = base_positions[finger_name]
            finger_info = self.finger_data[finger_name]
            segment_count = len(finger_info['segments'])
            
            # Get current angles for this finger
            if self.current_pose and finger_name in self.current_pose:
                target_angles = self.current_pose[finger_name]
                # Interpolate angles
                if self.animation_progress < 1:
                    start_angles = [0] * segment_count
                    current_angles = []
                    for i in range(segment_count):
                        current_angles.append(start_angles[i] + (target_angles[i] - start_angles[i]) * self.animation_progress)
                else:
                    current_angles = target_angles
            else:
                current_angles = [0] * segment_count
            
            # Draw finger segments
            current_x, current_y = base_pos
            segments_drawn = []
            
            for i, segment in enumerate(finger_info['segments']):
                segment_length = segment['length'] * self.scale
                segment_angle = current_angles[i] if i < len(current_angles) else 0
                
                # Add base angle for thumb
                if finger_name == 'thumb':
                    segment_angle += finger_info['base_angle']
                
                # Calculate end point
                end_x = current_x + math.cos(math.radians(segment_angle)) * segment_length
                end_y = current_y + math.sin(math.radians(segment_angle)) * segment_length
                
                # Draw finger segment
                segment_thickness = self.get_finger_thickness(finger_name, i, segment_count)
                self.draw_finger_segment(surface, (current_x, current_y), (end_x, end_y), 
                                       segment_thickness, finger_colors[finger_name])
                
                # Draw knuckle joint
                if i > 0:  # Don't draw joint at finger base (already drawn on palm)
                    joint_radius = max(3, (6 - i) * self.scale)
                    pygame.draw.circle(surface, self.knuckle_color, (int(current_x), int(current_y)), joint_radius)
                    pygame.draw.circle(surface, self.skin_highlight, 
                                     (int(current_x - joint_radius/2), int(current_y - joint_radius/2)), 
                                     max(1, joint_radius//2))
                
                segments_drawn.append(((current_x, current_y), (end_x, end_y)))
                current_x, current_y = end_x, end_y
            
            # Draw fingertip and nail
            self.draw_fingertip(surface, (current_x, current_y), finger_name, 
                              current_angles[-1] if current_angles else 0)
    
    def get_finger_thickness(self, finger_name, segment_index, total_segments):
        # Realistic finger tapering
        base_thickness = {
            'thumb': 14, 'index': 12, 'middle': 13, 'ring': 11, 'pinky': 9
        }[finger_name]
        
        # Taper towards tip
        taper_factor = 1.0 - (segment_index / total_segments) * 0.6
        return base_thickness * taper_factor
    
    def draw_finger_segment(self, surface, start, end, thickness, color):
        # Calculate direction
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
            
        # Normalize
        dx, dy = dx/length, dy/length
        
        # Calculate perpendicular
        perp_x, perp_y = -dy, dx
        
        # Calculate corners for filled segment
        half_thickness = thickness / 2
        corners = [
            (start[0] + perp_x * half_thickness, start[1] + perp_y * half_thickness),
            (start[0] - perp_x * half_thickness, start[1] - perp_y * half_thickness),
            (end[0] - perp_x * half_thickness, end[1] - perp_y * half_thickness),
            (end[0] + perp_x * half_thickness, end[1] + perp_y * half_thickness)
        ]
        
        # Draw filled segment
        pygame.draw.polygon(surface, color, corners)
        
        # Draw highlight on top
        highlight_corners = [
            (start[0] + perp_x * (half_thickness - 1), start[1] + perp_y * (half_thickness - 1)),
            (end[0] + perp_x * (half_thickness - 1), end[1] + perp_y * (half_thickness - 1)),
            (end[0] + perp_x * (half_thickness - 2), end[1] + perp_y * (half_thickness - 2)),
            (start[0] + perp_x * (half_thickness - 2), start[1] + perp_y * (half_thickness - 2))
        ]
        pygame.draw.polygon(surface, self.skin_highlight, highlight_corners)
    
    def draw_fingertip(self, surface, tip_pos, finger_name, angle):
        # Draw rounded fingertip
        tip_radius = {
            'thumb': 8, 'index': 6, 'middle': 7, 'ring': 6, 'pinky': 5
        }[finger_name] * self.scale
        
        # Draw fingertip circle
        pygame.draw.circle(surface, self.skin_base, tip_pos, tip_radius)
        
        # Draw nail (oval oriented with finger angle)
        nail_length = tip_radius * 1.5
        nail_width = tip_radius * 1.2
        
        # Create nail surface for rotation
        nail_surf = pygame.Surface((nail_length * 2, nail_width * 2), pygame.SRCALPHA)
        nail_rect = pygame.Rect(nail_length * 0.3, nail_width * 0.3, nail_length, nail_width)
        pygame.draw.ellipse(nail_surf, self.nail_color, nail_rect)
        
        # Rotate nail to match finger angle
        rotated_nail = pygame.transform.rotate(nail_surf, -angle)
        nail_pos = (tip_pos[0] - rotated_nail.get_width() // 2, 
                   tip_pos[1] - rotated_nail.get_height() // 2)
        
        surface.blit(rotated_nail, nail_pos)
        
        # Draw nail moon
        moon_pos = (tip_pos[0] + math.cos(math.radians(angle)) * tip_radius * 0.3,
                   tip_pos[1] + math.sin(math.radians(angle)) * tip_radius * 0.3)
        pygame.draw.circle(surface, (250, 240, 230), moon_pos, tip_radius * 0.3)
    
    def draw_rounded_rect(self, surface, rect, color, corner_radius):
        """Draw a rectangle with rounded corners"""
        pygame.draw.rect(surface, color, rect, border_radius=corner_radius)
        
        # Add some palm lines for realism
        line_y = rect.top + rect.height * 0.7
        pygame.draw.line(surface, self.skin_shadow, 
                        (rect.left + 10, line_y),
                        (rect.right - 10, line_y), 2)
        
        line_y2 = rect.top + rect.height * 0.5
        pygame.draw.line(surface, self.skin_shadow,
                        (rect.left + 15, line_y2),
                        (rect.right - 15, line_y2), 1)
    
    def draw_palm_creases(self, surface, palm_rect):
        # Draw major palm creases for realism
        crease_color = (200, 160, 120)
        
        # Heart line (upper crease)
        heart_start = (palm_rect.left + 20 * self.scale, palm_rect.top + 30 * self.scale)
        heart_end = (palm_rect.right - 10 * self.scale, palm_rect.top + 40 * self.scale)
        pygame.draw.arc(surface, crease_color, 
                       [heart_start[0], heart_start[1], 
                        heart_end[0] - heart_start[0], 20 * self.scale],
                       math.pi * 0.8, math.pi * 1.8, 2)
        
        # Head line (middle crease)
        head_start = (palm_rect.left + 15 * self.scale, palm_rect.top + 50 * self.scale)
        head_end = (palm_rect.right - 15 * self.scale, palm_rect.top + 55 * self.scale)
        pygame.draw.arc(surface, crease_color,
                       [head_start[0], head_start[1],
                        head_end[0] - head_start[0], 15 * self.scale],
                       math.pi * 0.7, math.pi * 1.9, 2)

# ----------------------------
# Character with Real Hands
# ----------------------------
class SignLanguageCharacter:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
        # Create realistic hands
        self.left_hand = RealHand(x - 150, y + 100, 1.2, False)
        self.right_hand = RealHand(x + 150, y + 100, 1.2, True)
        
        # Character properties
        self.head_radius = 60
        self.body_width = 120
        self.body_height = 200
        self.neck_length = 40
        
        # Animation state
        self.current_sign = None
        self.sign_timer = 0
        self.idle_animation = 0
        
    def set_sign(self, sign_name):
        self.current_sign = sign_name
        self.sign_timer = 0
        
        pose_mapping = {
            'hello': 'hello',
            'thank you': 'thank_you', 
            'i love you': 'i_love_you',
            'yes': 'yes',
            'no': 'no'
        }
        
        pose = pose_mapping.get(sign_name, 'rest')
        self.left_hand.set_pose(pose)
        self.right_hand.set_pose(pose)
    
    def update(self):
        self.idle_animation += 0.02
        self.sign_timer += 0.01
        
        self.left_hand.update()
        self.right_hand.update()
        
        if self.sign_timer > 3.0 and self.current_sign:
            self.current_sign = None
            self.left_hand.set_pose('rest')
            self.right_hand.set_pose('rest')
    
    def draw(self, surface):
        # Simple body silhouette
        body_rect = pygame.Rect(0, 0, self.body_width, self.body_height)
        body_rect.center = (self.x, self.y + self.body_height//2)
        pygame.draw.ellipse(surface, (80, 80, 100), body_rect)
        
        # Draw neck
        neck_start = (self.x, self.y - self.body_height//2 + 20)
        neck_end = (self.x, self.y - self.body_height//2 + 20 + self.neck_length)
        pygame.draw.line(surface, (200, 160, 120), neck_start, neck_end, 20)
        
        # Draw head
        head_pos = (self.x, self.y - self.body_height//2 - self.head_radius + 40)
        pygame.draw.circle(surface, (220, 180, 140), head_pos, self.head_radius)
        
        # Draw simple face
        self.draw_simple_face(surface, head_pos)
        
        # Draw arms
        arm_thickness = 25
        # Left arm
        pygame.draw.line(surface, (220, 180, 140), 
                        (self.x - self.body_width//2, self.y),
                        (self.left_hand.x, self.left_hand.y - 30), arm_thickness)
        # Right arm  
        pygame.draw.line(surface, (220, 180, 140),
                        (self.x + self.body_width//2, self.y),
                        (self.right_hand.x, self.right_hand.y - 30), arm_thickness)
        
        # Draw hands
        self.left_hand.draw(surface)
        self.right_hand.draw(surface)
    
    def draw_simple_face(self, surface, head_pos):
        # Eyes
        eye_y = head_pos[1] - 10
        left_eye = (head_pos[0] - 20, eye_y)
        right_eye = (head_pos[0] + 20, eye_y)
        
        pygame.draw.circle(surface, (255, 255, 255), left_eye, 8)
        pygame.draw.circle(surface, (255, 255, 255), right_eye, 8)
        pygame.draw.circle(surface, (80, 80, 120), left_eye, 4)
        pygame.draw.circle(surface, (80, 80, 120), right_eye, 4)
        
        # Mouth
        mouth_y = head_pos[1] + 15
        if self.current_sign == 'hello':
            # Smile
            pygame.draw.arc(surface, (200, 100, 100),
                           [head_pos[0] - 15, mouth_y - 5, 30, 20],
                           0, math.pi, 2)
        else:
            # Neutral
            pygame.draw.line(surface, (200, 100, 100),
                           (head_pos[0] - 10, mouth_y),
                           (head_pos[0] + 10, mouth_y), 2)

# ----------------------------
# UI Components
# ----------------------------
class Button:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.is_hovered = False
        
    def draw(self, surface):
        color = HIGHLIGHT_COLOR if self.is_hovered else ACCENT_COLOR
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=8)
        
        font = pygame.font.SysFont("Arial", 20)
        text_surf = font.render(self.text, True, TEXT_COLOR)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
        
    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered
        
    def is_clicked(self, pos, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(pos)
        return False

# ----------------------------
# Main Application
# ----------------------------
class SignLanguageApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Real Hand Sign Language")
        self.clock = pygame.time.Clock()
        
        self.font = pygame.font.SysFont("Arial", 24)
        self.title_font = pygame.font.SysFont("Arial", 36, bold=True)
        
        self.character = SignLanguageCharacter(WIDTH // 2, HEIGHT // 2)
        self.buttons = []
        self.create_buttons()
        
        self.input_text = ""
        
    def create_buttons(self):
        button_width, button_height = 160, 45
        start_x = 50
        start_y = HEIGHT - 120
        
        signs = [
            ("👋 Hello", "hello"),
            ("🙏 Thank You", "thank you"), 
            ("🤟 I Love You", "i love you"),
            ("👍 Yes", "yes"),
            ("👎 No", "no")
        ]
        
        for i, (text, sign) in enumerate(signs):
            x = start_x + (button_width + 15) * (i % 4)
            y = start_y + (button_height + 10) * (i // 4)
            self.buttons.append((Button(x, y, button_width, button_height, text), sign))
    
    def run(self):
        while True:
            mouse_pos = pygame.mouse.get_pos()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                    
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self.character.set_sign(self.input_text.lower())
                        self.input_text = ""
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    else:
                        self.input_text += event.unicode
                        
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    for button, sign in self.buttons:
                        if button.is_clicked(mouse_pos, event):
                            self.character.set_sign(sign)
            
            # Update hover states
            for button, _ in self.buttons:
                button.check_hover(mouse_pos)
            
            # Update character
            self.character.update()
            
            # Draw everything
            self.screen.fill(BACKGROUND_COLOR)
            
            # Draw title
            title = self.title_font.render("REAL HAND SIGN LANGUAGE", True, TEXT_COLOR)
            self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 20))
            
            # Draw input
            input_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT - 180, 400, 40)
            pygame.draw.rect(self.screen, UI_BG_COLOR, input_rect, border_radius=5)
            pygame.draw.rect(self.screen, ACCENT_COLOR, input_rect, 2, border_radius=5)
            
            input_surf = self.font.render(self.input_text, True, TEXT_COLOR)
            self.screen.blit(input_surf, (input_rect.x + 10, input_rect.y + 10))
            
            # Draw current sign
            if self.character.current_sign:
                sign_text = self.font.render(f"Signing: {self.character.current_sign.upper()}", True, HIGHLIGHT_COLOR)
                self.screen.blit(sign_text, (WIDTH//2 - sign_text.get_width()//2, 80))
            
            # Draw buttons
            for button, _ in self.buttons:
                button.draw(self.screen)
            
            # Draw character
            self.character.draw(self.screen)
            
            pygame.display.flip()
            self.clock.tick(FPS)

# Run the app
if __name__ == "__main__":
    app = SignLanguageApp()
    app.run()
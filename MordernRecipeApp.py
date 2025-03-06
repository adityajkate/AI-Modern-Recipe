import sys
import os
import json
import time
import threading
import sqlite3
from datetime import datetime
import random
import requests
from io import BytesIO
import speech_recognition as sr
from PIL import Image, ImageQt
import google.generativeai as genai

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QTextEdit, QCheckBox, QFrame, QScrollArea,
                           QStackedWidget, QSlider, QLineEdit, QComboBox, QFileDialog, 
                           QMessageBox, QTabWidget, QGridLayout, QSplashScreen, QProgressBar, QInputDialog)
from PyQt6.QtCore import (Qt, QPropertyAnimation, QEasingCurve, QTimer, QSize, 
                        QThread, pyqtSignal, QPoint, QRect, QParallelAnimationGroup, 
                        QSequentialAnimationGroup, QByteArray, QBuffer, pyqtProperty)
from PyQt6.QtGui import (QPixmap, QFont, QColor, QPalette, QIcon, QImage, 
                       QPainter, QBrush, QLinearGradient, QRadialGradient, 
                       QPainterPath, QCursor, QFontDatabase, QPen)

class CircularProgressBar(QWidget):
    def __init__(self, parent=None, value=0, width=200, height=200, progress_width=10, 
                 progress_color=QColor("#1DCDFE"), text_color=QColor("#FFFFFF"),
                 font_size=24):
        super().__init__(parent)
        self._value = value  # Use _value to avoid collision with property name
        self.width = width
        self.height = height
        self.progress_width = progress_width
        self.progress_color = progress_color
        self.text_color = text_color
        self.font_size = font_size
        self.setFixedSize(width, height)
        
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(1000)
        self.animation.setEasingCurve(QEasingCurve.Type.OutBack)
        
    def setValue(self, value):
        self.animation.setStartValue(self._value)  # Use _value here
        self.animation.setEndValue(value)
        self.animation.start()
    
    def get_value(self):
        return self._value  # Return _value instead
        
    def set_value(self, value):
        self._value = value  # Update _value instead of self.value
        self.update()
    
    # Define the property correctly
    value = pyqtProperty(int, get_value, set_value)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Setup coordinate system
        painter.translate(self.width / 2, self.height / 2)
        
        # Draw background circle
        bg_color = QColor("#3A3F44")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        
        # Calculate the ellipse dimensions (using integers)
        radius_x = int(self.width / 2 - self.progress_width / 2)
        radius_y = int(self.height / 2 - self.progress_width / 2)
        
        # Draw the background circle
        painter.drawEllipse(-radius_x, -radius_y, radius_x * 2, radius_y * 2)
        
        # Draw progress arc
        painter.setPen(QPen(self.progress_color, self.progress_width, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Calculate span angle (full circle = 5760, since Qt uses 16th of degrees)
        span_angle = int(-self._value * 5760 / 100)
        
        # Draw arc (start at 90 degrees = 1440 in Qt units)
        # Convert all values to integers for QRect
        rect_x = int(-self.width / 2 + self.progress_width / 2)
        rect_y = int(-self.height / 2 + self.progress_width / 2)
        rect_width = int(self.width - self.progress_width)
        rect_height = int(self.height - self.progress_width)
        
        painter.drawArc(
            QRect(rect_x, rect_y, rect_width, rect_height),
            1440, 
            span_angle
        )
        
        # Draw text
        painter.setPen(self.text_color)
        painter.setFont(QFont("Segoe UI", self.font_size, QFont.Weight.Bold))
        
        # Convert values to integers for QRect
        text_rect_x = int(-self.width / 2)
        text_rect_y = int(-self.height / 2)
        text_rect_width = int(self.width)
        text_rect_height = int(self.height)
        
        painter.drawText(
            QRect(text_rect_x, text_rect_y, text_rect_width, text_rect_height),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._value}%"
        )


class StylizedButton(QPushButton):
    def __init__(self, text="", parent=None, icon=None, gradient=True,
                primary_color="#1DCDFE", secondary_color="#2ecc71"):
        super().__init__(text, parent)
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.gradient = gradient
        self.setMinimumHeight(50)
        self.setFont(QFont("Segoe UI", 10))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        if icon:
            self.setIcon(QIcon(icon))
            self.setIconSize(QSize(24, 24))
        
        # Animations
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(100)
        
        # Add hover effect - grow slightly
        self.installEventFilter(self)
        
    def enterEvent(self, event):
        self.animation.setStartValue(self.geometry())
        target_geo = self.geometry()
        # Expand by 5 pixels on each side from center
        target_geo.setX(target_geo.x() - 2)
        target_geo.setY(target_geo.y() - 2)
        target_geo.setWidth(target_geo.width() + 4)
        target_geo.setHeight(target_geo.height() + 4)
        self.animation.setEndValue(target_geo)
        self.animation.start()
        return super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.animation.setStartValue(self.geometry())
        target_geo = self.geometry()
        target_geo.setX(target_geo.x() + 2)
        target_geo.setY(target_geo.y() + 2)
        target_geo.setWidth(target_geo.width() - 4)
        target_geo.setHeight(target_geo.height() - 4)
        self.animation.setEndValue(target_geo)
        self.animation.start()
        return super().leaveEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate rect with rounded corners
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        
        # Fill background
        if self.gradient:
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, QColor(self.primary_color))
            gradient.setColorAt(1, QColor(self.secondary_color))
            painter.fillPath(path, gradient)
        else:
            painter.fillPath(path, QBrush(QColor(self.primary_color)))
        
        # Draw text centered
        painter.setPen(QColor("white"))
        painter.setFont(self.font())
        
        # If has icon, adjust text position
        if not self.icon().isNull():
            icon_width = self.iconSize().width() + 10  # add some spacing
            text_rect = QRect(icon_width, 0, self.width() - icon_width, self.height())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())
            
            # Draw icon
            icon_rect = QRect(10, (self.height() - self.iconSize().height()) // 2,
                            self.iconSize().width(), self.iconSize().height())
            self.icon().paint(painter, icon_rect)
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

class AnimatedToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None, width=60, height=30, bg_color="#777", active_color="#1DCDFE"):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.bg_color = bg_color
        self.active_color = active_color
        self.circle_color = "#FFF"
        self.is_on = False
        self.animation = None
        self._circle_pos = 4
        
        # Set cursor type
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.height() // 2, self.height() // 2)
        
        if self.is_on:
            painter.fillPath(path, QColor(self.active_color))
        else:
            painter.fillPath(path, QColor(self.bg_color))
        
        # Draw circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.circle_color))
        circle_radius = (self.height() - 8) // 2
        painter.drawEllipse(self._circle_pos, 4, circle_radius * 2, circle_radius * 2)  # Use _circle_pos
    
    def mousePressEvent(self, e):
        self.toggle()
    
    def toggle(self):
        self.is_on = not self.is_on
        
        # Animate the circle
        if self.animation is None:
            self.animation = QPropertyAnimation(self, b"circle_pos")
            self.animation.setDuration(150)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        if self.is_on:
            self.animation.setStartValue(4)
            self.animation.setEndValue(self.width() - (self.height() - 4))
        else:
            self.animation.setStartValue(self.width() - (self.height() - 4))
            self.animation.setEndValue(4)
            
        self.animation.start()
        
        # Emit signal
        self.toggled.emit(self.is_on)
    
    def get_circle_pos(self):
        return self.circle_pos
        
    def set_circle_pos(self, pos):
        self.circle_pos = pos
        self.update()
    circle_pos = pyqtProperty(int, get_circle_pos, set_circle_pos)
    
    

class RecipeCardWidget(QFrame):
    clicked = pyqtSignal(int)  # Signal to emit when clicked, with recipe ID
    
    def __init__(self, recipe_id, name, image_path=None, parent=None):
        super().__init__(parent)
        self.recipe_id = recipe_id
        self.name = name
        
        # Set up appearance
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setObjectName("recipeCard")
        self.setStyleSheet("""
            #recipeCard {
                background-color: #2D3035;
                border-radius: 15px;
                border: none;
            }
            #recipeCardTitle {
                color: white;
                padding: 10px;
            }
            #recipeCard:hover {
                background-color: #40454B;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Image (if available)
        if image_path:
            image_label = QLabel()
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(250, 150, Qt.AspectRatioMode.KeepAspectRatio, 
                                     Qt.TransformationMode.SmoothTransformation)
                image_label.setPixmap(pixmap)
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(image_label)
        
        # Title
        title_label = QLabel(name)
        title_label.setObjectName("recipeCardTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Set fixed size
        self.setFixedSize(280, 200)
        
    def mousePressEvent(self, event):
        self.clicked.emit(self.recipe_id)
        return super().mousePressEvent(event)
    
    def enterEvent(self, event):
        # Scale up animation
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(100)
        animation.setStartValue(self.geometry())
        
        target_geo = self.geometry()
        target_geo.setX(target_geo.x() - 5)
        target_geo.setY(target_geo.y() - 5)
        target_geo.setWidth(target_geo.width() + 10)
        target_geo.setHeight(target_geo.height() + 10)
        
        animation.setEndValue(target_geo)
        animation.start()
        
        return super().enterEvent(event)
    
    def leaveEvent(self, event):
        # Scale down animation
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(100)
        animation.setStartValue(self.geometry())
        
        target_geo = self.geometry()
        target_geo.setX(target_geo.x() + 5)
        target_geo.setY(target_geo.y() + 5)
        target_geo.setWidth(target_geo.width() - 10)
        target_geo.setHeight(target_geo.height() - 10)
        
        animation.setEndValue(target_geo)
        animation.start()
        
        return super().leaveEvent(event)

class AIWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, api_key, prompt, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.prompt = prompt
    
    def run(self):
        try:
            # Configure the API
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Call API
            response = model.generate_content(self.prompt)
            response_text = response.text
            
            # Try to parse JSON
            try:
                # Find JSON content 
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    recipe_data = json.loads(json_text)
                    
                    # Ensure all required fields are present
                    required_fields = ["recipe_name", "prep_time", "cook_time", 
                                      "ingredients", "instructions"]
                    
                    for field in required_fields:
                        if field not in recipe_data:
                            if field == "recipe_name":
                                recipe_data["recipe_name"] = "Untitled Recipe"
                            elif field == "prep_time":
                                recipe_data["prep_time"] = "15 minutes"
                            elif field == "cook_time":
                                recipe_data["cook_time"] = "30 minutes"
                            elif field == "ingredients":
                                recipe_data["ingredients"] = ["Ingredients not specified"]
                            elif field == "instructions":
                                recipe_data["instructions"] = ["Instructions not available"]
                    
                    self.finished.emit(recipe_data)
                else:
                    # No valid JSON found, create a simple recipe
                    self.error.emit("Could not parse AI response as JSON")
            except json.JSONDecodeError:
                self.error.emit("Invalid JSON in AI response")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

class SpeechRecognitionWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def run(self):
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self.finished.emit("Listening...")
                
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source)
                
                # Listen for audio
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                self.finished.emit("Processing...")
                
                # Recognize speech
                text = recognizer.recognize_google(audio)
                self.finished.emit(text)
        except sr.WaitTimeoutError:
            self.error.emit("No speech detected")
        except sr.UnknownValueError:
            self.error.emit("Could not understand audio")
        except sr.RequestError:
            self.error.emit("Could not request results; check your network connection")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

class ModernRecipeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("AI Recipe Maker")
        self.setMinimumSize(1200, 800)
        
        # Initialize variables
        self.current_recipe = None
        self.favorites = []
        self.dark_mode = True
        self.filter_options = {
            "vegetarian": False,
            "vegan": False,
            "gluten_free": False,
            "keto": False,
            "low_carb": False
        }
        
        # API key - In production, this should be handled more securely
        self.api_key = ""  # Replace with your API key or get from environment
        if not self.api_key:
            self.api_key = os.environ.get("GEMINI_API_KEY", "")
        
        # Initialize database
        self.init_database()
        
        # Load fonts
        QFontDatabase.addApplicationFont(":/fonts/Montserrat-Bold.ttf")
        QFontDatabase.addApplicationFont(":/fonts/Montserrat-Regular.ttf")
        QFontDatabase.addApplicationFont(":/fonts/Montserrat-Medium.ttf")
        
        # Setup UI
        self.setup_ui()
        
        # Load favorites
        self.load_favorites()
        
        # Show splash animation
        self.show_splash_animation()
        
    def init_database(self):
        """Initialize SQLite database"""
        try:
            self.conn = sqlite3.connect('recipes.db')
            self.cursor = self.conn.cursor()
            
            # Create tables if they don't exist
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                image_url TEXT,
                prep_time TEXT,
                cook_time TEXT,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                FOREIGN KEY (recipe_id) REFERENCES recipes (id)
            )
            ''')
            
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dark_mode BOOLEAN DEFAULT 1,
                vegetarian BOOLEAN DEFAULT 0,
                vegan BOOLEAN DEFAULT 0,
                gluten_free BOOLEAN DEFAULT 0,
                keto BOOLEAN DEFAULT 0,
                low_carb BOOLEAN DEFAULT 0
            )
            ''')
            
            self.conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to initialize database: {e}")
    
    def setup_ui(self):
        """Set up the entire user interface"""
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout is horizontal
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Apply dark theme
        self.apply_dark_theme()
        
        # Create and add sidebar
        self.create_sidebar()
        main_layout.addWidget(self.sidebar)
        
        # Create stacked widget for main content
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)
        
        # Create all pages
        self.create_home_page()
        self.create_recipe_view_page()
        self.create_favorites_page()
        self.create_history_page()
        self.create_shopping_list_page()
        self.create_settings_page()
        
        # Add pages to stack
        self.content_stack.addWidget(self.home_page)
        self.content_stack.addWidget(self.recipe_view_page)
        self.content_stack.addWidget(self.favorites_page)
        self.content_stack.addWidget(self.history_page)
        self.content_stack.addWidget(self.shopping_list_page)
        self.content_stack.addWidget(self.settings_page)
        
        # Show home page by default
        self.content_stack.setCurrentIndex(0)
    
    def create_sidebar(self):
        """Create the sidebar with navigation buttons"""
        # Sidebar container
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet("""
            #sidebar {
                background-color: #1E2021;
                border-right: 1px solid #32383D;
            }
        """)
        
        # Sidebar layout
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(15)
        
        # Add logo/title
        logo_label = QLabel("AI Recipe Maker")
        logo_label.setObjectName("sidebarLogo")
        logo_label.setFont(QFont("Montserrat", 18, QFont.Weight.Bold))
        logo_label.setStyleSheet("color: #1DCDFE;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo_label)
        
        # Add separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #32383D;")
        sidebar_layout.addWidget(line)
        
        # Define menu items and icons
        menu_items = [
            {"text": "Home", "icon": ":/icons/home.png", "page": 0},
            {"text": "Recipe View", "icon": ":/icons/recipe.png", "page": 1},
            {"text": "Favorites", "icon": ":/icons/star.png", "page": 2},
            {"text": "History", "icon": ":/icons/history.png", "page": 3},
            {"text": "Shopping List", "icon": ":/icons/cart.png", "page": 4},
            {"text": "Settings", "icon": ":/icons/settings.png", "page": 5}
        ]
        
        # Create navigation buttons
        self.nav_buttons = []
        for item in menu_items:
            # Use custom button
            button = StylizedButton(
                text=item["text"],
                gradient=False,
                primary_color="#2D3035"
            )
            button.clicked.connect(lambda checked, page=item["page"]: self.content_stack.setCurrentIndex(page))
            sidebar_layout.addWidget(button)
            self.nav_buttons.append(button)
        
        # Add stretch to push version to bottom
        sidebar_layout.addStretch()
        
       
        version_label = QLabel("Created by AdityaKate ♡")
        version_label.setStyleSheet("color: #5D6570;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(version_label)
    
    def create_home_page(self):
        """Create the home page with recipe creation form"""
        self.home_page = QWidget()
        home_layout = QVBoxLayout(self.home_page)
        home_layout.setContentsMargins(30, 30, 30, 30)
        home_layout.setSpacing(20)
        
        # Page title
        title_label = QLabel("Create Your Recipe")
        title_label.setFont(QFont("Montserrat", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        home_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("Enter ingredients you have, and our AI will suggest delicious recipes!")
        desc_label.setFont(QFont("Montserrat", 12))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        home_layout.addWidget(desc_label)
        
        # Ingredients section
        ingredients_group = QFrame()
        ingredients_group.setObjectName("ingredientsGroup")
        ingredients_group.setStyleSheet("""
            #ingredientsGroup {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 15px;
            }
        """)
        ingredients_layout = QVBoxLayout(ingredients_group)
        
        # Title for ingredients
        ing_title = QLabel("Ingredients")
        ing_title.setFont(QFont("Montserrat", 14, QFont.Weight.Bold))
        ingredients_layout.addWidget(ing_title)
        
        # Ingredients input
        self.ingredients_input = QTextEdit()
        self.ingredients_input.setPlaceholderText("Enter ingredients separated by commas (e.g., chicken, rice, onion)")
        self.ingredients_input.setMinimumHeight(100)
        ingredients_layout.addWidget(self.ingredients_input)
        
        # Button row for ingredients
        ing_button_row = QHBoxLayout()
        
        # Voice input button
        self.voice_button = StylizedButton(
            text="Add by Voice",
            primary_color="#8E44AD",
            secondary_color="#9B59B6"
        )
        self.voice_button.clicked.connect(self.add_ingredients_by_voice)
        ing_button_row.addWidget(self.voice_button)
        
        # Clear button
        self.clear_button = StylizedButton(
            text="Clear",
            primary_color="#E74C3C",
            secondary_color="#C0392B"
        )
        self.clear_button.clicked.connect(lambda: self.ingredients_input.clear())
        ing_button_row.addWidget(self.clear_button)
        
        ingredients_layout.addLayout(ing_button_row)
        home_layout.addWidget(ingredients_group)
        
        # Dietary preferences section
        diet_group = QFrame()
        diet_group.setObjectName("dietGroup")
        diet_group.setStyleSheet("""
            #dietGroup {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 15px;
            }
        """)
        diet_layout = QVBoxLayout(diet_group)
        
        # Title for dietary preferences
        diet_title = QLabel("Dietary Preferences")
        diet_title.setFont(QFont("Montserrat", 14, QFont.Weight.Bold))
        diet_layout.addWidget(diet_title)
        
        # Checkboxes for dietary preferences
        diet_options_layout = QGridLayout()
        
        preferences = [
            ("Vegetarian", "vegetarian"),
            ("Vegan", "vegan"),
            ("Gluten-Free", "gluten_free"),
            ("Keto", "keto"),
            ("Low Carb", "low_carb")
        ]
        
        self.filter_checkboxes = {}
        row, col = 0, 0
        for label, key in preferences:
            checkbox = QCheckBox(label)
            checkbox.setChecked(self.filter_options[key])
            checkbox.stateChanged.connect(lambda state, k=key: self.update_filter_option(k, state))
            self.filter_checkboxes[key] = checkbox
            diet_options_layout.addWidget(checkbox, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        diet_layout.addLayout(diet_options_layout)
        home_layout.addWidget(diet_group)
        
        # Generate button with animation
        self.generate_button = StylizedButton(
            text="Generate Recipe",
            primary_color="#2ecc71",
            secondary_color="#27ae60"
        )
        self.generate_button.setFont(QFont("Montserrat", 14, QFont.Weight.Bold))
        self.generate_button.setMinimumHeight(60)
        self.generate_button.clicked.connect(self.generate_recipe)
        home_layout.addWidget(self.generate_button)
        
        # Progress indicator (hidden by default)
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("progressFrame")
        self.progress_frame.setStyleSheet("""
            #progressFrame {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 15px;
            }
        """)
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("Generating your recipe...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        progress_container = QFrame()
        progress_container_layout = QHBoxLayout(progress_container)
        self.progress_bar = CircularProgressBar(value=0)
        progress_container_layout.addWidget(self.progress_bar, 0, Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(progress_container)
        progress_layout.addWidget(self.progress_bar)
        
        home_layout.addWidget(self.progress_frame)
        self.progress_frame.hide()  # Hidden by default

    def create_recipe_view_page(self):
        """Create the recipe view page"""
        self.recipe_view_page = QWidget()
        recipe_layout = QVBoxLayout(self.recipe_view_page)
        recipe_layout.setContentsMargins(30, 30, 30, 30)
        recipe_layout.setSpacing(20)
        
        # Scroll area for recipe content
        recipe_scroll = QScrollArea()
        recipe_scroll.setWidgetResizable(True)
        recipe_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container widget for scroll area
        recipe_content = QWidget()
        self.recipe_content_layout = QVBoxLayout(recipe_content)
        self.recipe_content_layout.setContentsMargins(0, 0, 0, 0)
        self.recipe_content_layout.setSpacing(25)
        
        # Recipe title
        self.recipe_title = QLabel("No Recipe Selected")
        self.recipe_title.setFont(QFont("Montserrat", 24, QFont.Weight.Bold))
        self.recipe_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recipe_content_layout.addWidget(self.recipe_title)
        
        # Recipe info section
        recipe_info_frame = QFrame()
        recipe_info_frame.setObjectName("recipeInfoFrame")
        recipe_info_frame.setStyleSheet("""
            #recipeInfoFrame {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 15px;
            }
        """)
        recipe_info_layout = QHBoxLayout(recipe_info_frame)
        
        # Recipe image
        self.recipe_image = QLabel()
        self.recipe_image.setMinimumSize(300, 200)
        self.recipe_image.setMaximumSize(300, 200)
        self.recipe_image.setScaledContents(True)
        self.recipe_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recipe_image.setStyleSheet("background-color: #1E2021; border-radius: 10px;")
        recipe_info_layout.addWidget(self.recipe_image)
        
        # Recipe details
        recipe_details = QFrame()
        recipe_details_layout = QVBoxLayout(recipe_details)
        
        # Time information
        time_layout = QHBoxLayout()
        
        prep_time_label = QLabel("Prep Time:")
        prep_time_label.setFont(QFont("Montserrat", 12, QFont.Weight.Bold))
        time_layout.addWidget(prep_time_label)
        
        self.prep_time_value = QLabel("N/A")
        time_layout.addWidget(self.prep_time_value)
        
        time_layout.addStretch()
        
        cook_time_label = QLabel("Cook Time:")
        cook_time_label.setFont(QFont("Montserrat", 12, QFont.Weight.Bold))
        time_layout.addWidget(cook_time_label)
        
        self.cook_time_value = QLabel("N/A")
        time_layout.addWidget(self.cook_time_value)
        
        recipe_details_layout.addLayout(time_layout)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.favorite_button = StylizedButton(
            text="Add to Favorites",
            primary_color="#F39C12",
            secondary_color="#D35400"
        )
        self.favorite_button.clicked.connect(self.toggle_favorite)
        action_layout.addWidget(self.favorite_button)
        
        self.shopping_list_button = StylizedButton(
            text="Add to Shopping List", 
            primary_color="#3498DB",
            secondary_color="#2980B9"
        )
        self.shopping_list_button.clicked.connect(self.add_to_shopping_list)
        action_layout.addWidget(self.shopping_list_button)
        
        self.cooking_mode_button = StylizedButton(
            text="Start Cooking Mode",
            primary_color="#2ECC71",
            secondary_color="#27AE60"
        )
        self.cooking_mode_button.clicked.connect(self.start_cooking_mode)
        action_layout.addWidget(self.cooking_mode_button)
        
        recipe_details_layout.addLayout(action_layout)
        recipe_info_layout.addWidget(recipe_details)
        
        self.recipe_content_layout.addWidget(recipe_info_frame)
        
        # Ingredients section
        ingredients_frame = QFrame()
        ingredients_frame.setObjectName("ingredientsFrame")
        ingredients_frame.setStyleSheet("""
            #ingredientsFrame {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 15px;
            }
        """)
        ingredients_layout = QVBoxLayout(ingredients_frame)
        
        ingredients_title = QLabel("Ingredients")
        ingredients_title.setFont(QFont("Montserrat", 18, QFont.Weight.Bold))
        ingredients_layout.addWidget(ingredients_title)
        
        self.ingredients_list = QTextEdit()
        self.ingredients_list.setReadOnly(True)
        self.ingredients_list.setMinimumHeight(100)
        ingredients_layout.addWidget(self.ingredients_list)
        
        self.recipe_content_layout.addWidget(ingredients_frame)
        
        # Instructions section
        instructions_frame = QFrame()
        instructions_frame.setObjectName("instructionsFrame")
        instructions_frame.setStyleSheet("""
            #instructionsFrame {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 15px;
            }
        """)
        instructions_layout = QVBoxLayout(instructions_frame)
        
        instructions_title = QLabel("Instructions")
        instructions_title.setFont(QFont("Montserrat", 18, QFont.Weight.Bold))
        instructions_layout.addWidget(instructions_title)
        
        self.instructions_list = QTextEdit()
        self.instructions_list.setReadOnly(True)
        self.instructions_list.setMinimumHeight(200)
        instructions_layout.addWidget(self.instructions_list)
        
        self.recipe_content_layout.addWidget(instructions_frame)
        
        # Set the content widget
        recipe_scroll.setWidget(recipe_content)
        recipe_layout.addWidget(recipe_scroll)

    def create_favorites_page(self):
        """Create the favorites page"""
        self.favorites_page = QWidget()
        favorites_layout = QVBoxLayout(self.favorites_page)
        favorites_layout.setContentsMargins(30, 30, 30, 30)
        
        # Page title
        title_label = QLabel("Favorite Recipes")
        title_label.setFont(QFont("Montserrat", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        favorites_layout.addWidget(title_label)
        
        # Scroll area for recipe cards
        favorites_scroll = QScrollArea()
        favorites_scroll.setWidgetResizable(True)
        favorites_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container for recipe cards
        self.favorites_container = QWidget()
        self.favorites_grid_layout = QGridLayout(self.favorites_container)
        self.favorites_grid_layout.setContentsMargins(10, 10, 10, 10)
        self.favorites_grid_layout.setSpacing(20)
        
        # Empty message (shown if no favorites)
        self.no_favorites_label = QLabel("You haven't added any favorite recipes yet.")
        self.no_favorites_label.setFont(QFont("Montserrat", 14))
        self.no_favorites_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_favorites_label.setStyleSheet("color: #888;")
        self.favorites_grid_layout.addWidget(self.no_favorites_label, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)
        
        favorites_scroll.setWidget(self.favorites_container)
        favorites_layout.addWidget(favorites_scroll)

    def create_history_page(self):
        """Create the recipe history page"""
        self.history_page = QWidget()
        history_layout = QVBoxLayout(self.history_page)
        history_layout.setContentsMargins(30, 30, 30, 30)
        
        # Page title
        title_label = QLabel("Recipe History")
        title_label.setFont(QFont("Montserrat", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        history_layout.addWidget(title_label)
        
        # Scroll area for recipe history
        history_scroll = QScrollArea()
        history_scroll.setWidgetResizable(True)
        history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container for history items
        self.history_container = QWidget()
        self.history_container_layout = QVBoxLayout(self.history_container)
        self.history_container_layout.setContentsMargins(10, 10, 10, 10)
        self.history_container_layout.setSpacing(10)
        
        # Empty message (shown if no history)
        self.no_history_label = QLabel("You haven't created any recipes yet.")
        self.no_history_label.setFont(QFont("Montserrat", 14))
        self.no_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_history_label.setStyleSheet("color: #888;")
        self.history_container_layout.addWidget(self.no_history_label)
        
        # Add container to scroll area
        history_scroll.setWidget(self.history_container)
        history_layout.addWidget(history_scroll)
        
        # Refresh button
        refresh_button = StylizedButton(
            text="Refresh History",
            primary_color="#3498DB", 
            secondary_color="#2980B9"
        )
        refresh_button.clicked.connect(self.load_history)
        history_layout.addWidget(refresh_button)

    def create_shopping_list_page(self):
        """Create the shopping list page"""
        self.shopping_list_page = QWidget()
        shopping_layout = QVBoxLayout(self.shopping_list_page)
        shopping_layout.setContentsMargins(30, 30, 30, 30)
        
        # Page title
        title_label = QLabel("Shopping List")
        title_label.setFont(QFont("Montserrat", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shopping_layout.addWidget(title_label)
        
        # Scroll area for shopping items
        shopping_scroll = QScrollArea()
        shopping_scroll.setWidgetResizable(True)
        shopping_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Container for shopping items
        self.shopping_container = QWidget()
        self.shopping_container_layout = QVBoxLayout(self.shopping_container)
        self.shopping_container_layout.setContentsMargins(10, 10, 10, 10)
        self.shopping_container_layout.setSpacing(10)
        
        # Empty message (shown if empty)
        self.empty_shopping_list_label = QLabel("Your shopping list is empty.")
        self.empty_shopping_list_label.setFont(QFont("Montserrat", 14))
        self.empty_shopping_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_shopping_list_label.setStyleSheet("color: #888;")
        self.shopping_container_layout.addWidget(self.empty_shopping_list_label)
        
        shopping_scroll.setWidget(self.shopping_container)
        shopping_layout.addWidget(shopping_scroll)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        clear_button = StylizedButton(
            text="Clear List",
            primary_color="#E74C3C",
            secondary_color="#C0392B"
        )
        clear_button.clicked.connect(self.clear_shopping_list)
        button_layout.addWidget(clear_button)
        
        export_button = StylizedButton(
            text="Export List",
            primary_color="#3498DB",
            secondary_color="#2980B9"
        )
        export_button.clicked.connect(self.export_shopping_list)
        button_layout.addWidget(export_button)
        
        shopping_layout.addLayout(button_layout)
        
    def create_settings_page(self):
        """Create the settings page"""
        self.settings_page = QWidget()
        settings_layout = QVBoxLayout(self.settings_page)
        settings_layout.setContentsMargins(30, 30, 30, 30)
        
        # Page title
        title_label = QLabel("Settings")
        title_label.setFont(QFont("Montserrat", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout.addWidget(title_label)
        
        # Settings content
        settings_frame = QFrame()
        settings_frame.setObjectName("settingsFrame")
        settings_frame.setStyleSheet("""
            #settingsFrame {
                background-color: #2D3035;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        settings_frame_layout = QVBoxLayout(settings_frame)
        
        # API key setting
        api_key_layout = QHBoxLayout()
        
        api_key_label = QLabel("Gemini API Key:")
        api_key_label.setFont(QFont("Montserrat", 12))
        api_key_layout.addWidget(api_key_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Google Gemini API key")
        self.api_key_input.setText(self.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_layout.addWidget(self.api_key_input)
        
        save_api_key_btn = StylizedButton(
            text="Save", 
            primary_color="#2ECC71", 
            secondary_color="#27AE60"
        )
        save_api_key_btn.clicked.connect(self.save_api_key)
        api_key_layout.addWidget(save_api_key_btn)
        
        settings_frame_layout.addLayout(api_key_layout)
        
        # Appearance setting
        appearance_layout = QHBoxLayout()
        
        appearance_label = QLabel("Dark Mode:")
        appearance_label.setFont(QFont("Montserrat", 12))
        appearance_layout.addWidget(appearance_label)
        
        appearance_layout.addStretch()
        
        self.dark_mode_toggle = AnimatedToggleSwitch()
        self.dark_mode_toggle.is_on = self.dark_mode
        self.dark_mode_toggle.update()
        self.dark_mode_toggle.toggled.connect(self.toggle_theme)
        appearance_layout.addWidget(self.dark_mode_toggle)
        
        settings_frame_layout.addLayout(appearance_layout)
        
        # Default dietary preferences
        diet_pref_label = QLabel("Default Dietary Preferences:")
        diet_pref_label.setFont(QFont("Montserrat", 12, QFont.Weight.Bold))
        settings_frame_layout.addWidget(diet_pref_label)
        
        # Grid for diet preferences
        diet_grid = QGridLayout()
        
        preferences = [
            ("Vegetarian", "vegetarian"),
            ("Vegan", "vegan"),
            ("Gluten-Free", "gluten_free"),
            ("Keto", "keto"),
            ("Low Carb", "low_carb")
        ]
        
        self.settings_checkboxes = {}
        row, col = 0, 0
        for label, key in preferences:
            checkbox = QCheckBox(label)
            checkbox.setChecked(self.filter_options[key])
            self.settings_checkboxes[key] = checkbox
            diet_grid.addWidget(checkbox, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        settings_frame_layout.addLayout(diet_grid)
        
        # Add space
        settings_frame_layout.addStretch()
        
        # Save settings button
        save_settings_btn = StylizedButton(
            text="Save Settings", 
            primary_color="#2ECC71", 
            secondary_color="#27AE60"
        )
        save_settings_btn.clicked.connect(self.save_settings)
        settings_frame_layout.addWidget(save_settings_btn)
        
        settings_layout.addWidget(settings_frame)

    def apply_dark_theme(self):
        """Apply dark theme to the application"""
        self.setStyleSheet("""
            QWidget {
                background-color: #222529;
                color: #FFFFFF;
                font-family: 'Montserrat', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #32383D;
                color: #FFFFFF;
                border: 1px solid #40454B;
                border-radius: 5px;
                padding: 8px;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #1DCDFE;
            }
            QScrollArea, QScrollBar {
                background-color: #222529;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2D3035;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #40454B;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4D5258;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QCheckBox {
                color: #FFFFFF;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #40454B;
            }
            QCheckBox::indicator:unchecked {
                background-color: #32383D;
            }
            QCheckBox::indicator:checked {
                background-color: #1DCDFE;
                image: url(:/icons/check.png);
            }
            QFrame {
                border: none;
            }
        """)

    def apply_light_theme(self):
        """Apply light theme to the application"""
        self.setStyleSheet("""
            QWidget {
                background-color: #F5F5F7;
                color: #333333;
                font-family: 'Montserrat', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #333333;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #FFFFFF;
                color: #333333;
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                padding: 8px;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #1DCDFE;
            }
            QScrollArea, QScrollBar {
                background-color: #F5F5F7;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #FFFFFF;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #CCCCCC;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #BBBBBB;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QCheckBox {
                color: #333333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #CCCCCC;
            }
            QCheckBox::indicator:unchecked {
                background-color: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                background-color: #1DCDFE;
                image: url(:/icons/check.png);
            }
            QFrame {
                border: none;
            }
        """)

    def show_splash_animation(self):
        """Show a splash animation when app starts"""
        # Create a semi-transparent overlay
        self.splash_overlay = QWidget(self)
        self.splash_overlay.setGeometry(self.rect())
        self.splash_overlay.setStyleSheet("background-color: rgba(34, 37, 41, 0.9);")
        
        # Add logo and animation
        splash_layout = QVBoxLayout(self.splash_overlay)
        
        # Logo
        logo_label = QLabel("AI Recipe Maker")
        logo_label.setFont(QFont("Montserrat", 36, QFont.Weight.Bold))
        logo_label.setStyleSheet("color: #1DCDFE;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        splash_layout.addStretch(1)
        splash_layout.addWidget(logo_label)
        
        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(8)
        progress_bar.setMaximumWidth(400)
        progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #32383D;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #1DCDFE;
                border-radius: 4px;
            }
        """)
        splash_layout.addSpacing(20)
        splash_layout.addWidget(progress_bar, 0, Qt.AlignmentFlag.AlignCenter)
        splash_layout.addStretch(1)
        
        # Show overlay
        self.splash_overlay.show()
        
        # Animate progress bar
        self.splash_timer = QTimer()
        self.splash_progress = 0
        
        def update_progress():
            self.splash_progress += 4  # Increment progress
            progress_bar.setValue(self.splash_progress)
            
            # When complete, remove splash
            if self.splash_progress >= 100:
                self.splash_timer.stop()
                # Hide splash with fade out animation
                self.splash_fade = QPropertyAnimation(self.splash_overlay, b"windowOpacity")
                self.splash_fade.setStartValue(1.0)
                self.splash_fade.setEndValue(0.0)
                self.splash_fade.setDuration(500)
                self.splash_fade.finished.connect(self.splash_overlay.deleteLater)
                self.splash_fade.start()
        
        self.splash_timer.timeout.connect(update_progress)
        self.splash_timer.start(30)  # Update every 30ms

    def add_ingredients_by_voice(self):
        """Use speech recognition to add ingredients"""
        # Show status
        self.voice_button.setText("Listening...")
        self.voice_button.setEnabled(False)
        
        # Start worker thread
        self.speech_worker = SpeechRecognitionWorker()
        self.speech_worker.finished.connect(self.handle_speech_result)
        self.speech_worker.error.connect(self.handle_speech_error)
        self.speech_worker.start()

    def handle_speech_result(self, text):
        """Handle the result from speech recognition"""
        if text == "Listening..." or text == "Processing...":
            # Status update, not a result
            self.voice_button.setText(text)
            return
        
        # Get current ingredients
        current_text = self.ingredients_input.toPlainText().strip()
        
        # Add new ingredients
        if current_text:
            new_text = current_text + ", " + text
        else:
            new_text = text
        
        # Update textbox
        self.ingredients_input.setPlainText(new_text)
        
        # Reset button
        self.voice_button.setText("Add by Voice")
        self.voice_button.setEnabled(True)

    def handle_speech_error(self, error_message):
        """Handle speech recognition errors"""
        QMessageBox.warning(self, "Voice Input", error_message)
        self.voice_button.setText("Add by Voice")
        self.voice_button.setEnabled(True)

    def update_filter_option(self, key, state):
        """Update filter options when checkboxes are clicked"""
        self.filter_options[key] = state == Qt.CheckState.Checked

    def generate_recipe(self):
        """Generate a recipe based on the ingredients and filters"""
        # Get ingredients
        ingredients = self.ingredients_input.toPlainText().strip()
        
        if not ingredients:
            QMessageBox.warning(self, "Input Required", "Please enter some ingredients.")
            return
        
        if not self.api_key:
            QMessageBox.warning(self, "API Key Required", 
                            "Please set your Google Gemini API key in Settings.")
            return
        
        # Show progress indicator
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        
        # Disable generate button
        self.generate_button.setEnabled(False)
        self.generate_button.setText("Generating...")
        
        # Start progress animation
        self.progress_timer = QTimer()
        self.progress_value = 0
        
        def update_progress():
            if self.progress_value < 95:  # Leave room for completion
                self.progress_value += 1
                self.progress_bar.setValue(self.progress_value)
        
        self.progress_timer.timeout.connect(update_progress)
        self.progress_timer.start(100)  # Update every 100ms
        
        # Get active filters
        active_filters = []
        for filter_name, is_active in self.filter_options.items():
            if is_active:
                active_filters.append(filter_name.replace("_", " ").title())
        
        # Build prompt
        prompt = f"Create a detailed recipe using these ingredients: {ingredients}."
        
        if active_filters:
            prompt += f" The recipe should be {', '.join(active_filters)}."
        
        prompt += """ Return the response as a JSON object with the following structure:
        {
            "recipe_name": "Name of the recipe",
            "prep_time": "Preparation time",
            "cook_time": "Cooking time",
            "ingredients": ["Ingredient 1", "Ingredient 2", ...],
            "instructions": ["Step 1", "Step 2", ...],
            "image_prompt": "A detailed prompt to generate an image for this dish"
        }
        Only respond with the JSON object, no introduction or additional text.
        """
        
        # Start the AI worker thread
        self.ai_worker = AIWorker(self.api_key, prompt)
        self.ai_worker.finished.connect(self.handle_recipe_result)
        self.ai_worker.error.connect(self.handle_recipe_error)
        self.ai_worker.start()

    def handle_recipe_result(self, recipe_data):
        """Handle successful recipe generation"""
        # Stop progress animation
        self.progress_timer.stop()
        self.progress_bar.setValue(100)  # Complete the progress
        
        # Reset UI after a short delay
        QTimer.singleShot(500, lambda: self.reset_recipe_ui())
        
        # Save recipe to database
        self.save_recipe_to_db(recipe_data)
        
        # Display the recipe
        self.display_recipe(recipe_data)
        
        # Switch to recipe view page
        self.content_stack.setCurrentIndex(1)  # Recipe View page

    def handle_recipe_error(self, error_message):
        """Handle recipe generation errors"""
        # Stop progress animation
        self.progress_timer.stop()
        self.progress_frame.hide()
        
        # Reset button
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Recipe")
        
        # Show error
        QMessageBox.warning(self, "Generation Failed", error_message)

    def reset_recipe_ui(self):
        """Reset UI after recipe generation"""
        self.progress_frame.hide()
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Recipe")

    def save_recipe_to_db(self, recipe_data):
        """Save recipe to database"""
        try:
            # Convert lists to JSON strings
            ingredients_json = json.dumps(recipe_data.get("ingredients", []))
            instructions_json = json.dumps(recipe_data.get("instructions", []))
            
            # Insert recipe into database
            self.cursor.execute("""
            INSERT INTO recipes (name, ingredients, instructions, prep_time, cook_time)
            VALUES (?, ?, ?, ?, ?)
            """, (
                recipe_data.get("recipe_name", "Untitled Recipe"),
                ingredients_json,
                instructions_json,
                recipe_data.get("prep_time", "N/A"),
                recipe_data.get("cook_time", "N/A")
            ))
            
            self.conn.commit()
            
            # Get the ID of the newly inserted recipe
            recipe_id = self.cursor.lastrowid
            
            # Store the ID for reference
            self.current_recipe = recipe_id
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to save recipe: {e}")

    def display_recipe(self, recipe_data):
        """Display the recipe in the recipe view page"""
        # Update recipe title
        self.recipe_title.setText(recipe_data.get("recipe_name", "Untitled Recipe"))
        
        # Update times
        self.prep_time_value.setText(recipe_data.get("prep_time", "N/A"))
        self.cook_time_value.setText(recipe_data.get("cook_time", "N/A"))
        
        # Update ingredients
        self.ingredients_list.clear()
        for ingredient in recipe_data.get("ingredients", []):
            self.ingredients_list.append(f"• {ingredient}")
        
        # Update instructions
        self.instructions_list.clear()
        for i, instruction in enumerate(recipe_data.get("instructions", []), 1):
            self.instructions_list.append(f"{i}. {instruction}\n")
        
        # Set placeholder image
        self.set_placeholder_image()
        
        # Update favorite button state
        if self.current_recipe in self.favorites:
            self.favorite_button.setText("Remove from Favorites")
            self.favorite_button.primary_color = "#E74C3C"
            self.favorite_button.secondary_color = "#C0392B"
        else:
            self.favorite_button.setText("Add to Favorites")
            self.favorite_button.primary_color = "#F39C12"
            self.favorite_button.secondary_color = "#D35400"
        self.favorite_button.update()

    def set_placeholder_image(self):
        """Set a placeholder image for the recipe"""
        # Create a placeholder image with a gradient background and food icon
        image = QImage(300, 200, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create gradient background
        gradient = QLinearGradient(0, 0, 300, 200)
        gradient.setColorAt(0, QColor(45, 48, 53))
        gradient.setColorAt(1, QColor(32, 35, 40))
        painter.fillRect(0, 0, 300, 200, gradient)
        
        # Draw a plate icon or food symbol in the center
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(200, 200, 200, 80))
        painter.drawEllipse(100, 50, 100, 100)
        
        painter.setPen(QPen(QColor(150, 150, 150), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(115, 65, 70, 70)
        
        # Draw a fork and knife
        painter.drawLine(150, 80, 150, 120)
        painter.drawLine(130, 100, 170, 100)
        
        painter.end()
        
        # Set the image
        pixmap = QPixmap.fromImage(image)
        self.recipe_image.setPixmap(pixmap)

    def load_recipe(self, recipe_id):
        """Load a recipe from the database by ID"""
        try:
            # Query recipe data
            self.cursor.execute("""
            SELECT name, ingredients, instructions, image_url, prep_time, cook_time
            FROM recipes WHERE id = ?
            """, (recipe_id,))
            
            result = self.cursor.fetchone()
            if result:
                name, ingredients_json, instructions_json, image_url, prep_time, cook_time = result
                
                # Parse JSON strings
                ingredients = json.loads(ingredients_json)
                instructions = json.loads(instructions_json)
                
                # Create recipe data structure
                recipe_data = {
                    "recipe_name": name,
                    "ingredients": ingredients,
                    "instructions": instructions,
                    "prep_time": prep_time,
                    "cook_time": cook_time
                }
                
                # Store the current recipe ID
                self.current_recipe = recipe_id
                
                # Display the recipe
                self.display_recipe(recipe_data)
                
                # Switch to recipe view
                self.content_stack.setCurrentIndex(1)  # Recipe View page
                
        except (sqlite3.Error, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Error", f"Failed to load recipe: {e}")

    def toggle_favorite(self):
        """Toggle the current recipe as favorite"""
        if not self.current_recipe:
            QMessageBox.information(self, "No Recipe", "No recipe is currently selected.")
            return
        
        if self.current_recipe in self.favorites:
            # Remove from favorites
            try:
                self.cursor.execute("DELETE FROM favorites WHERE recipe_id = ?", (self.current_recipe,))
                self.conn.commit()
                self.favorites.remove(self.current_recipe)
                
                # Update button
                self.favorite_button.setText("Add to Favorites")
                self.favorite_button.primary_color = "#F39C12"
                self.favorite_button.secondary_color = "#D35400"
                self.favorite_button.update()
                
                # Show notification
                QMessageBox.information(self, "Removed from Favorites", 
                                    "This recipe has been removed from your favorites.")
                
                # Refresh favorites page if it's visible
                if self.content_stack.currentIndex() == 2:  # Favorites page
                    self.load_favorites_page()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to remove from favorites: {e}")
        else:
            # Add to favorites
            try:
                self.cursor.execute("INSERT INTO favorites (recipe_id) VALUES (?)", (self.current_recipe,))
                self.conn.commit()
                self.favorites.append(self.current_recipe)
                
                # Update button
                self.favorite_button.setText("Remove from Favorites")
                self.favorite_button.primary_color = "#E74C3C"
                self.favorite_button.secondary_color = "#C0392B"
                self.favorite_button.update()
                
                # Show notification
                QMessageBox.information(self, "Added to Favorites", 
                                    "This recipe has been added to your favorites.")
                
                # Refresh favorites page if it's visible
                if self.content_stack.currentIndex() == 2:  # Favorites page
                    self.load_favorites_page()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to add to favorites: {e}")

    def load_favorites(self):
        """Load favorite recipes from the database"""
        try:
            self.cursor.execute("SELECT recipe_id FROM favorites")
            self.favorites = [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error:
            self.favorites = []

    def load_favorites_page(self):
        """Load favorites into the favorites page"""
        # Clear existing content
        for i in reversed(range(self.favorites_grid_layout.count())): 
            widget = self.favorites_grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        if not self.favorites:
            # Show "no favorites" message
            self.no_favorites_label = QLabel("You haven't added any favorite recipes yet.")
            self.no_favorites_label.setFont(QFont("Montserrat", 14))
            self.no_favorites_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.no_favorites_label.setStyleSheet("color: #888;")
            self.favorites_grid_layout.addWidget(self.no_favorites_label, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)
            return
        
        # If we have favorites, load them as cards
        try:
            row, col = 0, 0
            max_cols = 3  # 3 cards per row
            
            for recipe_id in self.favorites:
                self.cursor.execute("SELECT name FROM recipes WHERE id = ?", (recipe_id,))
                result = self.cursor.fetchone()
                
                if result:
                    recipe_name = result[0]
                    
                    # Create recipe card
                    card = RecipeCardWidget(recipe_id, recipe_name)
                    card.clicked.connect(self.load_recipe)
                    
                    self.favorites_grid_layout.addWidget(card, row, col)
                    
                    # Update position
                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1
            
            # Add stretch to bottom
            self.favorites_grid_layout.setRowStretch(row + 1, 1)
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load favorites: {e}")

    def load_history(self):
        """Load recipe history"""
        # Clear existing history items
        for i in reversed(range(self.history_container_layout.count())):
            widget = self.history_container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        try:
            # Get recent recipes from database
            self.cursor.execute(
                "SELECT id, name, date_added FROM recipes ORDER BY date_added DESC LIMIT 20"
            )
            history = self.cursor.fetchall()
            
            if not history:
                # Show empty message
                self.no_history_label = QLabel("You haven't created any recipes yet.")
                self.no_history_label.setFont(QFont("Montserrat", 14))
                self.no_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.no_history_label.setStyleSheet("color: #888;")
                self.history_container_layout.addWidget(self.no_history_label)
                return
            
            # Add history items
            for recipe_id, name, date in history:
                # Create history item frame
                history_item = QFrame()
                history_item.setObjectName("historyItem")
                history_item.setStyleSheet("""
                    #historyItem {
                        background-color: #2D3035;
                        border-radius: 10px;
                        padding: 10px;
                    }
                    #historyItem:hover {
                        background-color: #40454B;
                    }
                """)
                
                item_layout = QHBoxLayout(history_item)
                
                # Recipe name and date
                date_str = date.split(" ")[0] if " " in date else date
                item_text = QLabel(f"{name} - {date_str}")
                item_text.setFont(QFont("Montserrat", 12))
                item_layout.addWidget(item_text)
                
                item_layout.addStretch()
                
                # View button
                view_btn = StylizedButton("View Recipe", gradient=False, primary_color="#3498DB")
                view_btn.setFixedWidth(120)
                view_btn.clicked.connect(lambda checked, rid=recipe_id: self.load_recipe(rid))
                item_layout.addWidget(view_btn)
                
                self.history_container_layout.addWidget(history_item)
            
            # Add stretch to bottom
            self.history_container_layout.addStretch()
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load history: {e}")

    def add_to_shopping_list(self):
        """Add current recipe ingredients to the shopping list"""
        if not self.current_recipe:
            QMessageBox.information(self, "No Recipe", "No recipe is currently selected.")
            return
        
        try:
            # Get recipe ingredients
            self.cursor.execute("SELECT name, ingredients FROM recipes WHERE id = ?", (self.current_recipe,))
            result = self.cursor.fetchone()
            
            if result:
                recipe_name, ingredients_json = result
                ingredients = json.loads(ingredients_json)
                
                # Remove empty label if it exists
                if hasattr(self, 'empty_shopping_list_label'):
                    self.empty_shopping_list_label.setParent(None)
                    delattr(self, 'empty_shopping_list_label')
                
                # Create shopping list item
                item_frame = QFrame()
                item_frame.setObjectName("shoppingItem")
                item_frame.setStyleSheet("""
                    #shoppingItem {
                        background-color: #2D3035;
                        border-radius: 10px;
                        padding: 15px;
                    }
                """)
                
                item_layout = QVBoxLayout(item_frame)
                
                # Recipe name header
                header = QLabel(recipe_name)
                header.setFont(QFont("Montserrat", 14, QFont.Weight.Bold))
                item_layout.addWidget(header)
                
                # Ingredients with checkboxes
                for ingredient in ingredients:
                    check_layout = QHBoxLayout()
                    
                    checkbox = QCheckBox(ingredient)
                    checkbox.setFont(QFont("Montserrat", 12))
                    check_layout.addWidget(checkbox)
                    
                    item_layout.addLayout(check_layout)
                
                # Add to shopping list container
                self.shopping_container_layout.insertWidget(self.shopping_container_layout.count() - 1, item_frame)
                
                # Switch to shopping list page
                self.content_stack.setCurrentIndex(4)  # Shopping List page
                
                QMessageBox.information(self, "Added to Shopping List", 
                                    f"Ingredients for {recipe_name} added to your shopping list.")
                
        except (sqlite3.Error, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Error", f"Failed to add to shopping list: {e}")

    def clear_shopping_list(self):
        """Clear the shopping list"""
        # Ask for confirmation
        reply = QMessageBox.question(
            self, "Clear List", 
            "Are you sure you want to clear your shopping list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove all shopping items
            for i in reversed(range(self.shopping_container_layout.count())):
                widget = self.shopping_container_layout.itemAt(i).widget()
                if widget and widget != self.empty_shopping_list_label:
                    widget.setParent(None)
            
            # Add empty message back
            if not hasattr(self, 'empty_shopping_list_label') or not self.empty_shopping_list_label.isVisible():
                self.empty_shopping_list_label = QLabel("Your shopping list is empty.")
                self.empty_shopping_list_label.setFont(QFont("Montserrat", 14))
                self.empty_shopping_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.empty_shopping_list_label.setStyleSheet("color: #888;")
                self.shopping_container_layout.addWidget(self.empty_shopping_list_label)

    def export_shopping_list(self):
        """Export the shopping list to a file"""
        # Check if shopping list is empty
        if (hasattr(self, 'empty_shopping_list_label') and 
            self.empty_shopping_list_label.isVisible()):
            QMessageBox.information(self, "Empty List", "Your shopping list is empty.")
            return
        
        # Ask for file location
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Shopping List", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return  # User canceled
        
        try:
            with open(file_path, 'w') as file:
                file.write("SHOPPING LIST\n")
                file.write("=============\n\n")
                
                # Go through each shopping item
                for i in range(self.shopping_container_layout.count()):
                    widget = self.shopping_container_layout.itemAt(i).widget()
                    if isinstance(widget, QFrame) and widget.objectName() == "shoppingItem":
                        # Get the recipe name from the first label
                        recipe_name = None
                        for child in widget.children():
                            if isinstance(child, QLabel):
                                recipe_name = child.text()
                                break
                        
                        if recipe_name:
                            file.write(f"{recipe_name}\n")
                            file.write("-" * len(recipe_name) + "\n")
                            
                            # Write ingredients
                            for child in widget.findChildren(QCheckBox):
                                ingredient = child.text()
                                checked = child.isChecked()
                                status = "[x]" if checked else "[ ]"
                                file.write(f"{status} {ingredient}\n")
                            
                            file.write("\n")
                
            QMessageBox.information(self, "Export Successful", f"Shopping list exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export shopping list: {e}")
    
    def start_cooking_mode(self):
        """Start the step-by-step cooking mode"""
        if not self.current_recipe:
            QMessageBox.information(self, "No Recipe", "No recipe is currently selected.")
            return
        
        try:
            # Get recipe details
            self.cursor.execute("""
                SELECT name, instructions, prep_time, cook_time 
                FROM recipes WHERE id = ?
            """, (self.current_recipe,))
            
            result = self.cursor.fetchone()
            if not result:
                QMessageBox.critical(self, "Error", "Recipe not found!")
                return
                
            name, instructions_json, prep_time, cook_time = result
            instructions = json.loads(instructions_json)
            
            if not instructions:
                QMessageBox.warning(self, "No Instructions", "This recipe has no cooking instructions.")
                return
            
            # Create cooking mode window
            cooking_window = QMainWindow(self)
            cooking_window.setWindowTitle(f"Cooking: {name}")
            cooking_window.setMinimumSize(800, 600)
            cooking_window.setStyleSheet(self.styleSheet())  # Inherit style
            
            # Central widget
            central_widget = QWidget()
            cooking_window.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(30, 30, 30, 30)
            
            # Title bar
            title_bar = QFrame()
            title_bar.setObjectName("cookingTitleBar")
            title_bar.setStyleSheet("""
                #cookingTitleBar {
                    background-color: #2D3035;
                    border-radius: 15px;
                    padding: 15px;
                    margin-bottom: 20px;
                }
            """)
            title_bar_layout = QHBoxLayout(title_bar)
            
            # Title
            title = QLabel(f"Cooking: {name}")
            title.setFont(QFont("Montserrat", 18, QFont.Weight.Bold))
            title_bar_layout.addWidget(title)
            
            # Times
            times_label = QLabel(f"Prep: {prep_time} | Cook: {cook_time}")
            times_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            title_bar_layout.addWidget(times_label)
            
            main_layout.addWidget(title_bar)
            
            # Step display
            step_frame = QFrame()
            step_frame.setObjectName("stepFrame")
            step_frame.setStyleSheet("""
                #stepFrame {
                    background-color: #2D3035;
                    border-radius: 15px;
                    padding: 20px;
                }
            """)
            step_layout = QVBoxLayout(step_frame)
            
            # Step progress
            progress_layout = QHBoxLayout()
            
            step_progress_label = QLabel("Step 1 of 0")  # Will be updated
            step_progress_label.setFont(QFont("Montserrat", 14))
            progress_layout.addWidget(step_progress_label)
            
            step_progress = QProgressBar()
            step_progress.setRange(0, len(instructions))
            step_progress.setValue(1)
            step_progress.setFixedHeight(10)
            step_progress.setTextVisible(False)
            step_progress.setStyleSheet("""
                QProgressBar {
                    background-color: #32383D;
                    border-radius: 5px;
                }
                QProgressBar::chunk {
                    background-color: #1DCDFE;
                    border-radius: 5px;
                }
            """)
            progress_layout.addWidget(step_progress)
            
            step_layout.addLayout(progress_layout)
            
            # Step text
            step_text = QLabel()
            step_text.setFont(QFont("Montserrat", 16))
            step_text.setWordWrap(True)
            step_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_text.setMinimumHeight(200)
            step_layout.addWidget(step_text)
            
            # Timer section
            timer_frame = QFrame()
            timer_frame.setObjectName("timerFrame")
            timer_frame.setStyleSheet("""
                #timerFrame {
                    background-color: #32383D;
                    border-radius: 10px;
                    padding: 10px;
                }
            """)
            timer_layout = QHBoxLayout(timer_frame)
            
            timer_label = QLabel("Timer:")
            timer_label.setFont(QFont("Montserrat", 14))
            timer_layout.addWidget(timer_label)
            
            timer_display = QLabel("00:00")
            timer_display.setFont(QFont("Montserrat", 14, QFont.Weight.Bold))
            timer_layout.addWidget(timer_display)
            
            timer_start_btn = StylizedButton("Start Timer")
            timer_layout.addWidget(timer_start_btn)
            
            timer_layout.addStretch()
            
            step_layout.addWidget(timer_frame)
            
            # Navigation buttons
            nav_layout = QHBoxLayout()
            
            prev_button = StylizedButton(
                "Previous Step", 
                primary_color="#7F8C8D",
                secondary_color="#95A5A6"
            )
            prev_button.setEnabled(False)  # Disabled for first step
            nav_layout.addWidget(prev_button)
            
            nav_layout.addStretch()
            
            next_button = StylizedButton(
                "Next Step", 
                primary_color="#2ECC71",
                secondary_color="#27AE60"
            )
            nav_layout.addWidget(next_button)
            
            step_layout.addLayout(nav_layout)
            
            main_layout.addWidget(step_frame)
            
            # Timer section
            timer_running = [False]
            timer_seconds = [0]
            timer_id = [None]
            
            # Update functions
            def update_step(step_index):
                if 0 <= step_index < len(instructions):
                    step_text.setText(instructions[step_index])
                    step_progress_label.setText(f"Step {step_index + 1} of {len(instructions)}")
                    step_progress.setValue(step_index + 1)
                    
                    # Update button states
                    prev_button.setEnabled(step_index > 0)
                    
                    if step_index == len(instructions) - 1:
                        next_button.setText("Finish")
                    else:
                        next_button.setText("Next Step")
            
            def handle_timer():
                if timer_running[0]:
                    timer_seconds[0] -= 1
                    minutes = timer_seconds[0] // 60
                    seconds = timer_seconds[0] % 60
                    timer_display.setText(f"{minutes:02d}:{seconds:02d}")
                    
                    if timer_seconds[0] <= 0:
                        stop_timer()
                        timer_display.setText("00:00")
                        QMessageBox.information(cooking_window, "Timer", "Time's up!")
            
            def start_timer():
                if timer_running[0]:
                    # Stop the timer
                    stop_timer()
                    timer_start_btn.setText("Start Timer")
                else:
                    # Ask for minutes
                    time_text, ok = QInputDialog.getText(
                        cooking_window, "Set Timer", "Enter time in minutes:"
                    )
                    
                    if ok:
                        try:
                            minutes = float(time_text)
                            timer_seconds[0] = int(minutes * 60)
                            
                            if timer_seconds[0] > 0:
                                # Start the timer
                                timer_running[0] = True
                                timer_start_btn.setText("Stop Timer")
                                
                                # Update display
                                minutes = timer_seconds[0] // 60
                                seconds = timer_seconds[0] % 60
                                timer_display.setText(f"{minutes:02d}:{seconds:02d}")
                                
                                # Create timer
                                timer_id[0] = QTimer()
                                timer_id[0].timeout.connect(handle_timer)
                                timer_id[0].start(1000)  # 1 second
                            else:
                                QMessageBox.warning(cooking_window, "Invalid Input", 
                                                 "Please enter a positive number of minutes.")
                        except ValueError:
                            QMessageBox.warning(cooking_window, "Invalid Input", 
                                             "Please enter a valid number of minutes.")
            
            def stop_timer():
                timer_running[0] = False
                if timer_id[0]:
                    timer_id[0].stop()
            
            # Save current step
            current_step = [0]
            
            # Button handlers
            def next_step():
                if current_step[0] < len(instructions) - 1:
                    current_step[0] += 1
                    update_step(current_step[0])
                else:
                    # Finish cooking
                    cooking_window.close()
                    QMessageBox.information(self, "Cooking Complete", 
                                         "Congratulations! You have completed all the steps.")
            
            def prev_step():
                if current_step[0] > 0:
                    current_step[0] -= 1
                    update_step(current_step[0])
            
            # Connect signals
            next_button.clicked.connect(next_step)
            prev_button.clicked.connect(prev_step)
            timer_start_btn.clicked.connect(start_timer)
            
            # Show first step
            update_step(0)
            
            # Show cooking window
            cooking_window.show()
            
        except (sqlite3.Error, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Error", f"Failed to start cooking mode: {e}")
    
    def save_api_key(self):
        """Save the API key"""
        api_key = self.api_key_input.text().strip()
        self.api_key = api_key
        QMessageBox.information(self, "API Key Saved", "Your API key has been saved.")
    
    def save_settings(self):
        """Save user settings"""
        try:
            # Save filter preferences
            for key, checkbox in self.settings_checkboxes.items():
                self.filter_options[key] = checkbox.isChecked()
            
            # Update filter checkboxes on home page
            for key, value in self.filter_options.items():
                if key in self.filter_checkboxes:
                    self.filter_checkboxes[key].setChecked(value)
            
            # Save to database
            self.cursor.execute("SELECT COUNT(*) FROM user_preferences")
            count = self.cursor.fetchone()[0]
            
            if count == 0:
                # Insert new preferences
                self.cursor.execute("""
                INSERT INTO user_preferences (
                    dark_mode, vegetarian, vegan, gluten_free, keto, low_carb
                ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.dark_mode,
                    self.filter_options["vegetarian"],
                    self.filter_options["vegan"],
                    self.filter_options["gluten_free"],
                    self.filter_options["keto"],
                    self.filter_options["low_carb"]
                ))
            else:
                # Update preferences
                self.cursor.execute("""
                UPDATE user_preferences SET 
                    dark_mode = ?, 
                    vegetarian = ?, 
                    vegan = ?, 
                    gluten_free = ?, 
                    keto = ?, 
                    low_carb = ?
                WHERE id = 1
                """, (
                    self.dark_mode,
                    self.filter_options["vegetarian"],
                    self.filter_options["vegan"],
                    self.filter_options["gluten_free"],
                    self.filter_options["keto"],
                    self.filter_options["low_carb"]
                ))
            
            self.conn.commit()
            QMessageBox.information(self, "Settings Saved", "Your settings have been saved.")
        
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to save settings: {e}")
    
    def toggle_theme(self, dark_mode):
        """Toggle between dark and light theme"""
        self.dark_mode = dark_mode
        if dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

# Main application entry point
def main():
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Set application icon and style
    app.setStyle("Fusion")
    
    # Create main window
    window = ModernRecipeApp()
    window.show()
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
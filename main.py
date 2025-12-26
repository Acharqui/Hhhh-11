from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, BooleanProperty, DictProperty, NumericProperty
from kivy.clock import Clock, mainthread
from kivy.utils import platform, get_color_from_hex
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.uix.relativelayout import RelativeLayout
from datetime import datetime, timedelta
import threading
import requests
import json
import os
import time
import sqlite3
from collections import OrderedDict

from kivy.core.clipboard import Clipboard 

from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.list import OneLineListItem, TwoLineListItem, OneLineIconListItem
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineAvatarIconListItem
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.card import MDCard
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout

if platform not in ("android", "ios"):
    Window.size = (400, 800)


class SQLiteStorage:
    def __init__(self, db_name='football_data.db'):
        """تهيئة التخزين مع قاعدة بيانات خارجية على أندرويد"""
        self.db_path = self._get_external_db_path(db_name)
        self._ensure_db_directory()
        self.init_database()
        print(f"📁 قاعدة البيانات في: {self.db_path}")
    
    def _get_external_db_path(self, db_name):
        """الحصول على مسار قاعدة البيانات في التخزين الخارجي على أندرويد"""
        if platform == 'android':
            try:
                # استيراد مكتبات أندرويد
                from android.storage import primary_external_storage_path
                from android.permissions import request_permissions, Permission
                
                # طلب إذن الكتابة في التخزين الخارجي (لأندرويد 10 وما دون)
                try:
                    permissions = [Permission.WRITE_EXTERNAL_STORAGE,
                                 Permission.READ_EXTERNAL_STORAGE]
                    request_permissions(permissions)
                    time.sleep(1)  # الانتظار قليلاً لمنح الإذن
                except Exception as e:
                    print(f"⚠️ ملاحظة على الإذن: {e}")
                    # تجاهل الخطأ إذا كان الإذن ممنوحًا بالفعل
                
                # الحصول على المسار الرئيسي للتخزين الخارجي
                try:
                    ext_storage = primary_external_storage_path()
                    print(f"📁 التخزين الخارجي: {ext_storage}")
                    
                    # إنشاء مجلد خاص بالتطبيق
                    app_folder = os.path.join(ext_storage, "FootballAppData")
                    os.makedirs(app_folder, exist_ok=True)
                    
                    # المسار النهائي للقاعدة
                    return os.path.join(app_folder, db_name)
                    
                except Exception as e:
                    print(f"⚠️ خطأ في الوصول للتخزين الخارجي: {e}")
                    # استخدام المسار الافتراضي كخيار احتياطي
                    return db_name
                    
            except Exception as e:
                print(f"⚠️ خطأ في تهيئة التخزين الخارجي: {e}")
                return db_name
        else:
            # لنظام التشغيل الآخر (ويندوز، لينكس، ماك)
            import tempfile
            app_folder = os.path.join(tempfile.gettempdir(), "FootballAppData")
            os.makedirs(app_folder, exist_ok=True)
            return os.path.join(app_folder, db_name)
    
    def _ensure_db_directory(self):
        """تأكد من وجود مجلد قاعدة البيانات"""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"📁 تم إنشاء مجلد قاعدة البيانات: {db_dir}")
        except Exception as e:
            print(f"⚠️ خطأ في إنشاء مجلد قاعدة البيانات: {e}")
    
    def init_database(self):
        """تهيئة جداول قاعدة البيانات"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # جدول المباريات المفضلة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY,
                    match_data TEXT
                )
            ''')
            
            # جدول المباريات المخفية
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hidden_matches (
                    id INTEGER PRIMARY KEY,
                    match_data TEXT
                )
            ''')
            
            # جدول الدوريات المفضلة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorite_leagues (
                    id INTEGER PRIMARY KEY,
                    league_name TEXT,
                    league_id INTEGER UNIQUE
                )
            ''')
            
            # جدول الدوريات المحددة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS selected_leagues (
                    id INTEGER PRIMARY KEY,
                    league_name TEXT,
                    league_id INTEGER UNIQUE
                )
            ''')
            
            # جدول إعدادات الفلتر
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS filter_settings (
                    id INTEGER PRIMARY KEY,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT
                )
            ''')
            
            # جدول جديد: كاش API الرئيسي
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    params_hash TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    access_count INTEGER DEFAULT 0,
                    UNIQUE(endpoint, params_hash)
                )
            ''')
            
            # فهارس لتحسين الأداء
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_cache_lookup
                ON api_cache(endpoint, params_hash)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_api_cache_expires
                ON api_cache(expires_at)
            ''')
            
            # جدول جديد: إحصائيات استخدام الكاش
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    cache_hits INTEGER DEFAULT 0,
                    cache_misses INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    UNIQUE(date)
                )
            ''')
            
            conn.commit()
            conn.close()
            
            print("✅ تم تهيئة قاعدة البيانات بنجاح")
            
        except Exception as e:
            print(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    # دوال المباريات المفضلة
    def load_favorites(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT match_data FROM favorites')
        rows = cursor.fetchall()
        conn.close()
        
        favorites = []
        for row in rows:
            try:
                match_data = json.loads(row[0])
                favorites.append(match_data)
            except:
                pass
        return favorites
    
    def save_favorites(self, favorites):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # مسح القديم وإضافة الجديد
        cursor.execute('DELETE FROM favorites')
        
        for match in favorites:
            try:
                match_data = json.dumps(match)
                cursor.execute('INSERT INTO favorites (match_data) VALUES (?)', (match_data,))
            except:
                pass
        
        conn.commit()
        conn.close()
    
    # دوال المباريات المخفية
    def load_hidden_matches(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT match_data FROM hidden_matches')
        rows = cursor.fetchall()
        conn.close()
        
        hidden_matches = []
        for row in rows:
            try:
                match_data = json.loads(row[0])
                hidden_matches.append(match_data)
            except:
                pass
        return hidden_matches
    
    def save_hidden_matches(self, hidden_matches):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM hidden_matches')
        
        for match in hidden_matches:
            try:
                match_data = json.dumps(match)
                cursor.execute('INSERT INTO hidden_matches (match_data) VALUES (?)', (match_data,))
            except:
                pass
        
        conn.commit()
        conn.close()
    
    # دوال الدوريات المفضلة
    def load_favorite_leagues(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT league_name, league_id FROM favorite_leagues')
        rows = cursor.fetchall()
        conn.close()
        
        favorite_leagues = []
        for row in rows:
            favorite_leagues.append({'name': row[0], 'id': row[1]})
        return favorite_leagues
    
    def save_favorite_leagues(self, favorite_leagues):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM favorite_leagues')
        
        for league in favorite_leagues:
            try:
                cursor.execute('INSERT INTO favorite_leagues (league_name, league_id) VALUES (?, ?)',
                             (league['name'], league['id']))
            except:
                pass
        
        conn.commit()
        conn.close()
    
    # دوال الدوريات المحددة
    def load_league_selection(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT league_name, league_id FROM selected_leagues')
        rows = cursor.fetchall()
        conn.close()
        
        selected_leagues = []
        for row in rows:
            selected_leagues.append({'name': row[0], 'id': row[1]})
        return selected_leagues
    
    def save_league_selection(self, selected_leagues):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM selected_leagues')
        
        for league in selected_leagues:
            try:
                cursor.execute('INSERT INTO selected_leagues (league_name, league_id) VALUES (?, ?)',
                             (league['name'], league['id']))
            except:
                pass
        
        conn.commit()
        conn.close()
    
    # دوال إعدادات الفلتر
    def load_filter_state(self, setting_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM filter_settings WHERE setting_name = ?', (setting_name,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0] == 'True'
        return False
    
    def save_filter_state(self, setting_name, state):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO filter_settings (setting_name, setting_value)
            VALUES (?, ?)
        ''', (setting_name, str(state)))
        
        conn.commit()
        conn.close()


class CalendarHeader(MDBoxLayout):
    selected_date = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self.current_date = datetime.now().date()
        self.min_date = datetime.now().date() - timedelta(days=30)
        self.max_date = datetime.now().date() + timedelta(days=365)
        self.update_display()
    
    def update_display(self):
        today = datetime.now().date()
        
        if hasattr(self, 'ids'):
            if 'prev_btn' in self.ids:
                self.ids.prev_btn.disabled = self.current_date <= self.min_date
            if 'next_btn' in self.ids:
                self.ids.next_btn.disabled = self.current_date >= self.max_date
        
        if self.current_date == today:
            self.selected_date = "TODAY"
        elif self.current_date == today + timedelta(days=1):
            self.selected_date = "TOMORROW"
        elif self.current_date == today + timedelta(days=2):
            self.selected_date = "DAY AFTER"
        else:
            self.selected_date = self.current_date.strftime('%d/%m/%Y')
    
    def previous_day(self):
        new_date = self.current_date - timedelta(days=1)
        if new_date >= self.min_date:
            self.current_date = new_date
            self.update_display()
            self.app.on_calendar_date_selected(self.current_date)
    
    def next_day(self):
        new_date = self.current_date + timedelta(days=1)
        if new_date <= self.max_date:
            self.current_date = new_date
            self.update_display()
            self.app.on_calendar_date_selected(self.current_date)


class StatsPopup(MDFloatLayout):
    home_team_name = StringProperty("")
    away_team_name = StringProperty("")
    first_team_name_display = StringProperty("")
    second_team_name_display = StringProperty("")
    first_team_goals_for = StringProperty("0")
    first_team_goals_against = StringProperty("0")
    second_team_goals_for = StringProperty("0")
    second_team_goals_against = StringProperty("0")
    first_team_label = StringProperty("") 
    second_team_label = StringProperty("")
    first_team_color = StringProperty("green")
    second_team_color = StringProperty("green")
    
    first_team_current_rank = StringProperty("-")
    first_team_last_rank = StringProperty("-")
    first_team_points = StringProperty("-")
    first_team_played = StringProperty("-")
    
    second_team_current_rank = StringProperty("-")
    second_team_last_rank = StringProperty("-")
    second_team_points = StringProperty("-")
    second_team_played = StringProperty("-")
    
    first_last_rank_color = StringProperty("#AAAAAA")
    second_last_rank_color = StringProperty("#AAAAAA")
    
    def copy_team_rank_info(self, team_type, copy_type="current"):
        try:
            if team_type == 'first':
                current_rank = self.first_team_current_rank
                last_rank = self.first_team_last_rank
                opponent_current_rank = self.second_team_current_rank
                opponent_last_rank = self.second_team_last_rank
                team_name = self.first_team_name_display
            elif team_type == 'second':
                current_rank = self.second_team_current_rank
                last_rank = self.second_team_last_rank
                opponent_current_rank = self.first_team_current_rank
                opponent_last_rank = self.first_team_last_rank
                team_name = self.second_team_name_display
            else:
                MDApp.get_running_app().show_snackbar("❌ خطأ: نوع الفريق غير معروف")
                return

            def clean_rank(rank):
                cleaned = ''.join(filter(str.isdigit, str(rank))) 
                return cleaned if cleaned else '0'

            if copy_type == "current":
                team_rank = clean_rank(current_rank)
                opponent_rank = clean_rank(opponent_current_rank)
                copied_text = f"{team_rank}{opponent_rank}"
                message_type = "الترتيب الحالي"
            else:  
                team_rank = clean_rank(last_rank)
                opponent_rank = clean_rank(opponent_last_rank)
                copied_text = f"{team_rank}{opponent_rank}"
                message_type = "ترتيب الموسم الماضي"

            # نسخ إلى الحافظة
            Clipboard.copy(copied_text)
            MDApp.get_running_app().show_snackbar(
                f"✅ تم نسخ {message_type} لـ {team_name}: {copied_text}", 
                duration=3
            )
            
            print(f"📋 تم النسخ: {copied_text} للفريق {team_name} ({message_type})")
            
        except Exception as e:
            print(f"❌ خطأ في النسخ: {e}")
            MDApp.get_running_app().show_snackbar(f"❌ فشل النسخ: {e}")


class LeagueItem(OneLineAvatarIconListItem):
    def __init__(self, league_name, league_id, **kwargs):
        super().__init__(**kwargs)
        self.text = league_name
        self.league_id = league_id
        self.selected = False

    def toggle_checkbox(self):
        self.selected = not self.selected
        self.ids.check.icon = "checkbox-marked" if self.selected else "checkbox-blank-outline"


class FavoriteLeagueItem(OneLineAvatarIconListItem):
    def __init__(self, league_name, league_id, **kwargs):
        super().__init__(**kwargs)
        self.text = league_name
        self.league_id = league_id

    def remove_favorite(self):
        app = MDApp.get_running_app()
        app.remove_favorite_league(self.league_id)


class LoadingWidget(MDBoxLayout):
    loading_text = StringProperty("Loading data...")
    progress_value = NumericProperty(0)
    status_text = StringProperty("Initializing...")


class ErrorWidget(MDBoxLayout):
    error_text = StringProperty("Loading error")


class OptimizedCompactMatchItem(MDCard):
    match_data = DictProperty({})
    is_fav = BooleanProperty(False)
    is_live = BooleanProperty(False)
    
    league_name = StringProperty("")
    home_team = StringProperty("")
    away_team = StringProperty("")
    home_score = StringProperty("-")
    away_score = StringProperty("-")
    full_score = StringProperty("VS")
    match_status = StringProperty("")
    match_time = StringProperty("")
    events_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(match_data=self.on_match_data)

    def on_match_data(self, instance, value):
        if value:
            self.update_display()

    def update_display(self):
        try:
            self.league_name = self.match_data.get('league', 'Loading...')
            
            home_team_name = self.match_data.get('home_team', 'Home Team')
            away_team_name = self.match_data.get('away_team', 'Away Team')
            
            if len(home_team_name) > 15:
                self.home_team = home_team_name[:12] + "..."
            else:
                self.home_team = home_team_name

            if len(away_team_name) > 15:
                self.away_team = away_team_name[:12] + "..."
            else:
                self.away_team = away_team_name

            home_score = self.match_data.get('home_score')
            away_score = self.match_data.get('away_score')
            
            self.home_score = str(home_score) if home_score is not None else "-"
            self.away_score = str(away_score) if away_score is not None else "-"
            
            if home_score is not None and away_score is not None:
                self.full_score = f"{home_score}-{away_score}"
            else:
                self.full_score = "VS"
            
            status = self.match_data.get('status', 'NS')
            self.match_status = self.get_status_text(status)
            self.match_time = self.get_time_text(status)
            self.is_live = status in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']
            
            if self.is_live:
                self.md_bg_color = get_color_from_hex("000000") 
                self.elevation = 2 
            else:
                self.md_bg_color = get_color_from_hex("#FFFFFF")
                self.elevation = 1
            
        except Exception as e:
            print(f"Display update error: {e}")

    def get_status_text(self, status):
        status_map = {
            'NS': 'NS', '1H': '1H', 'HT': 'HT',
            '2H': '2H', 'ET': 'ET', 'P': 'P',
            'FT': 'FT', 'AET': 'AET', 'PEN': 'PEN',
            'BT': 'BT', 'SUSP': 'SUSP', 'INT': 'INT',
            'PST': 'PST', 'CANC': 'CANC', 'LIVE': 'LIVE'
        }
        return status_map.get(status, status)

    def get_time_text(self, status):
        if status in ['1H', '2H', 'LIVE']:
            elapsed = self.match_data.get('elapsed')
            return f"{elapsed}'" if elapsed else "Live"
        elif status == 'HT':
            return "HT"
        elif status == 'ET':
            return "ET"
        elif status == 'P':
            return "PEN"
        elif status == 'NS':
            time_str = self.match_data.get('time', '')
            if time_str:
                try:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return dt.strftime('%H:%M')
                except:
                    return time_str[:16]
        return self.match_status

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            hide_button = self.ids.hide_button
            
            safe_area_limit = self.x + self.width * 0.85
            
            if hide_button.collide_point(*touch.pos):
                return super().on_touch_down(touch)
            elif touch.x < safe_area_limit:
                touch.ud['in_match_item'] = True
                return True 
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            hide_button = self.ids.hide_button
            
            safe_area_limit = self.x + self.width * 0.85
            
            if not hide_button.collide_point(*touch.pos) and touch.x < safe_area_limit:
                app = MDApp.get_running_app()
                app.show_stats_popup_improved(self.match_data)
                return True
                
        return super().on_touch_up(touch)

    def hide_match(self):
        app = MDApp.get_running_app()
        match_id = self.match_data.get('id')
        
        # تحقق إذا كانت المباراة في القائمة المخفية
        is_in_hidden_list = app.is_hidden(match_id)
        
        if not is_in_hidden_list:
            # إخفاء المباراة: إضافتها إلى القائمة المخفية
            app.add_hidden_match(self.match_data)
            app.show_snackbar(f"✅ Match hidden: {self.home_team} vs {self.away_team}")
            
            # إزالة المباراة من جميع القوائم مباشرة
            app.remove_match_from_all_lists(match_id)
            
            # إزالة الودجت من الشاشة
            parent = self.parent
            if parent:
                parent.remove_widget(self)
        else:
            # إزالة المباراة من القائمة المخفية
            app.remove_hidden_match(match_id)
            app.show_snackbar(f"✅ Match unhidden: {self.home_team} vs {self.away_team}")
            
            # إزالة الودجت من الشاشة
            parent = self.parent
            if parent:
                parent.remove_widget(self)


KV = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex
#:import dp kivy.metrics.dp
#:import Animation kivy.animation.Animation

<CalendarHeader>:
    size_hint_y: None
    height: dp(50)
    orientation: 'horizontal'
    spacing: dp(10)
    padding: dp(5)
    
    MDIconButton:
        id: prev_btn
        icon: 'chevron-left'
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3")
        on_release: root.previous_day()
        
    MDRaisedButton:
        id: date_btn
        text: root.selected_date
        size_hint_x: 0.7
        md_bg_color: get_color_from_hex("#2196F3")
        
    MDIconButton:
        id: next_btn
        icon: 'chevron-right'
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3")
        on_release: root.next_day()

<StatsPopup>:
    size_hint: None, None
    size: dp(210), dp(170)
    pos_hint: {'center_x': 0.5, 'center_y': 0.9}
    md_bg_color: get_color_from_hex("#000000")
    radius: dp(45)
    opacity: 0
    
    MDBoxLayout:
        orientation: 'vertical'
        spacing: dp(5)
        padding: dp(15)
        pos_hint: {'center_x': 0.5, 'center_y': 0.5}
        
        MDLabel:
            text: ""
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#FFFFFF")
            font_style: 'Caption'
            halign: 'center'
            bold: True
            size_hint_y: None
            height: dp(25)
        
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: dp(15)
            size_hint_y: None
            height: dp(60)
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(0)
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(2)
                    size_hint_y: None
                    height: dp(5)
                    
                    MDLabel:
                        text: root.first_team_name_display
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FFFFFF")
                        font_size: "12sp"
                        halign: 'center'
                        bold: True
                        text_size: self.width, None
                        size_hint_x: 0.5
                        
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    
                    MDIconButton:
                        icon: 'home'
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#2196F3")
                        icon_size: "15sp"
                        size_hint_x: 1
                        pos_hint: {"center_y": 0.5}
                        on_release: root.copy_team_rank_info('first', 'current')
                        

                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(0)
                    
                    MDLabel:
                        text: root.first_team_goals_for
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.first_team_color == 'green' else (get_color_from_hex("#2196F3") if root.first_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.first_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
                        
                    MDLabel:
                        text: ":"
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.first_team_color == 'green' else (get_color_from_hex("#2196F3") if root.first_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.first_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "9sp"
                        halign: 'center'
                        size_hint_x: 0.1
                        
                    MDLabel:
                        text: root.first_team_goals_against
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FF0000")
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(0)
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(2)
                    size_hint_y: None
                    height: dp(5)
                    
                    MDLabel:
                        text: root.second_team_name_display
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FFFFFF")
                        font_size: "12sp"
                        halign: 'center'
                        bold: True
                        text_size: self.width, None
                        size_hint_x: 0.5
                        
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(10)
                    
                    MDIconButton:
                        icon: 'calendar-clock'
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FF9800")
                        icon_size: "15sp"
                        size_hint_x: 1
                        pos_hint: {"center_y": 0.5}
                        on_release: root.copy_team_rank_info('first', 'last')
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(0)
                    
                    MDLabel:
                        text: root.second_team_goals_for
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.second_team_color == 'green' else (get_color_from_hex("#2196F3") if root.second_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.second_team_color == 'red'else get_color_from_hex("#FFFFFF")))
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
                        
                    MDLabel:
                        text: ":"
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00") if root.second_team_color == 'green' else (get_color_from_hex("#2196F3") if root.second_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.second_team_color == 'red' else get_color_from_hex("#FFFFFF")))
                        font_size: "9sp"
                        halign: 'center'
                        size_hint_x: 0.1
                        
                    MDLabel:
                        text: root.second_team_goals_against
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FF0000")
                        font_size: "21sp"
                        halign: 'center'
                        bold: True
        
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: dp(15)
            size_hint_y: None
            height: dp(40)
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(2)
                
                MDLabel:
                    text: "Classement"
                    theme_text_color: 'Custom'
                    text_color: get_color_from_hex("#FFFFFF")
                    font_size: "8sp"
                    halign: 'center'
                
                MDBoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(5)
                    
                    MDLabel:
                        text: root.first_team_current_rank
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#00FF00")
                        font_size: "15sp"
                        halign: 'center'
                        bold: True
                        
                    MDLabel:
                        text: "(" + root.first_team_last_rank + ")"
                        theme_text_color: 'Custom'
                        text_color: root.first_last_rank_color
                        font_size: "15sp"
                        halign: 'center'
            
            MDLabel:
                text: "|"
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#666666")
                font_size: "12sp"
                halign: 'center'
                size_hint_x: 0.1
            
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.35
                spacing: dp(2)
                
                MDBoxLayout:
                    orientation: 'vertical'
                    spacing: dp(5)

                    MDLabel:
                        text: "Classement"
                        theme_text_color: 'Custom'
                        text_color: get_color_from_hex("#FFFFFF")
                        font_size: "8sp"
                        halign: 'center'
                    
                    MDBoxLayout:
                        orientation: 'horizontal'
                        spacing: dp(5)
                        
                        MDLabel:
                            text: root.second_team_current_rank
                            theme_text_color: 'Custom'
                            text_color: get_color_from_hex("#00FF00")
                            font_size: "15sp"
                            halign: 'center'
                            bold: True
                            
                        MDLabel:
                            text: "(" + root.second_team_last_rank + ")"
                            theme_text_color: 'Custom'
                            text_color: root.second_last_rank_color
                            font_size: "15sp"
                            halign: 'center'

<LeagueItem>:
    IconLeftWidget:
        id: check
        icon: "checkbox-blank-outline"
        on_release: root.toggle_checkbox()

<FavoriteLeagueItem>:
    IconLeftWidget:
        icon: "star"
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#FFD700")

<LoadingWidget>:
    orientation: 'vertical'
    spacing: dp(20)
    padding: dp(20)
    size_hint_y: None
    height: dp(150)

    MDLabel:
        text: root.loading_text
        halign: 'center'
        theme_text_color: 'Secondary'
        font_style: 'H6'
        bold: True

    MDProgressBar:
        id: progress_bar
        value: root.progress_value
        type: "determinate"
        
    MDLabel:
        id: progress_text
        text: f"{int(root.progress_value)}%"
        halign: 'center'
        theme_text_color: 'Primary'
        font_style: 'H5'
        bold: True

    MDLabel:
        id: status_text
        text: root.status_text
        halign: 'center'
        theme_text_color: 'Secondary'
        font_style: 'Caption'

<ErrorWidget>:
    orientation: 'vertical'
    spacing: dp(20)
    padding: dp(20)
    size_hint_y: None
    height: dp(150)

    MDIcon:
        icon: "wifi-off"
        size_hint: None, None
        size: dp(48), dp(48)
        pos_hint: {'center_x': 0.5}
        theme_text_color: 'Secondary'

    MDLabel:
        text: root.error_text
        halign: 'center'
        theme_text_color: 'Secondary'

    MDRaisedButton:
        text: "Retry"
        pos_hint: {'center_x': 0.5}
        on_release: app.retry_loading()

<OptimizedCompactMatchItem>:
    size_hint_y: None
    height: dp(80)
    x: 0
    md_bg_color: get_color_from_hex("000000") if root.is_live else get_color_from_hex("#FFFFFF")
    elevation: 2 if root.is_live else 1
    padding: dp(8)
    radius: dp(8)
    orientation: 'horizontal'
    spacing: dp(6)

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.20
        spacing: dp(2)
        
        MDLabel:
            text: root.match_time
            font_style: 'Caption'
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#FF0000") if root.is_live else get_color_from_hex("#666666")
            halign: 'center'
            bold: True
            font_size: '16sp'
            
        MDLabel:
            text: root.league_name
            font_style: 'Caption'
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#FFFFFF") if root.is_live else get_color_from_hex("#999999")
            halign: 'center'
            font_size: '9sp'
            shorten: True
            shorten_from: 'right'
            text_size: self.width, None

    BoxLayout:
        orientation: 'horizontal'
        size_hint_x: 0.65
        spacing: dp(5)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_x: 0.48
            spacing: dp(3)
            
            MDLabel:
                text: root.home_team
                font_style: 'Body2'
                halign: 'right'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FFFFFF") if root.is_live else get_color_from_hex("#000000")
                shorten: True
                shorten_from: 'right'
                font_size: '12sp'
                text_size: self.width, None
                
            MDLabel:
                text: root.home_score
                font_style: 'Subtitle1'
                halign: 'center'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("FFFFFF") if root.is_live else get_color_from_hex("#000000")
                bold: True
                font_size: '18sp'
                size_hint_x: 0.28

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.12
            spacing: dp(2)
            
            MDLabel:
                text: root.match_status
                font_style: 'Caption'
                halign: 'center'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FF0000") if root.is_live else get_color_from_hex("#666666")
                bold: root.is_live
                font_size: '10sp'

        BoxLayout:
            orientation: 'horizontal'
            size_hint_x: 0.48
            spacing: dp(3)
            
            MDLabel:
                text: root.away_score
                font_style: 'Subtitle1'
                halign: 'center'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("FFFFFF") if root.is_live else get_color_from_hex("#000000")
                bold: True
                font_size: '18sp'
                size_hint_x: 0.28
                
            MDLabel:
                text: root.away_team
                font_style: 'Body2'
                halign: 'left'
                theme_text_color: 'Custom'
                text_color: get_color_from_hex("#FFFFFF") if root.is_live else get_color_from_hex("#000000")
                shorten: True
                shorten_from: 'left'
                font_size: '12sp'
                text_size: self.width, None

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.15
        spacing: dp(2)
        
        MDIconButton:
            id: hide_button
            icon: 'eye-off'
            user_font_size: '20sp'
            theme_text_color: 'Custom'
            text_color: get_color_from_hex("#FF5252")
            on_release: root.hide_match()
            size_hint_y: 1

<BottomNavButton@MDFloatLayout>:
    size_hint: None, None
    size: dp(80), dp(70)
    icon: ''
    text: ''
    selected: False

    MDIconButton:
        icon: root.icon
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3") if root.selected else get_color_from_hex("#757575")
        pos_hint: {'center_x': 0.5, 'center_y': 0.6}
        user_font_size: '24sp'
        on_release: app.switch_tab(root.text.lower())

    MDLabel:
        text: root.text
        theme_text_color: 'Custom'
        text_color: get_color_from_hex("#2196F3") if root.selected else get_color_from_hex("#757575")
        font_style: 'Caption'
        halign: 'center'
        pos_hint: {'center_x': 0.5, 'center_y': 0.2}

BoxLayout:
    orientation: 'vertical'
    spacing: 0

    MDTopAppBar:
        id: topbar
        title: app.current_title
        elevation: 0
        md_bg_color: get_color_from_hex("#2196F3")
        specific_text_color: get_color_from_hex("#FFFFFF")
        left_action_items: 
            [
            ['arrow-left', lambda x: app.go_back()],
            ['menu', lambda x: app.open_menu()]
            ]
        right_action_items: 
            [
            ['autorenew', lambda x: app.actualaser_refresh()],
            ['update', lambda x: app.manual_refresh()]
            ]
        height: dp(52)

    RelativeLayout:
        id: stats_popup_container
        size_hint_y: None
        height: 0

    CalendarHeader:
        id: calendar_header

    BoxLayout:
        orientation: 'vertical'
        spacing: dp(6)
        padding: dp(6)

        BoxLayout:
            size_hint_y: None
            height: dp(35)
            spacing: dp(8)

            MDLabel:
                text: app.current_time
                font_style: 'H1'
                halign: 'center'
                theme_text_color: 'Primary'
                font_size: '1sp'
                size_hint_x: 1
                bold: True

        ScrollView:
            id: main_scroll
            MDGridLayout:
                id: main_list
                cols: 1
                adaptive_height: True
                spacing: dp(6)
                padding: dp(4)

    BoxLayout:
        id: bottom_nav
        size_hint_y: None
        height: dp(65)
        md_bg_color: get_color_from_hex("#FFFFFF")
        padding: dp(6)
        spacing: dp(4)

        BottomNavButton:
            id: btn_en_cours
            icon: 'play-circle'
            text: 'Live'
            selected: True

        BottomNavButton:
            id: btn_favoris
            icon: 'star'
            text: 'Favorites'

        BottomNavButton:
            id: btn_competitions
            icon: 'trophy'
            text: 'Leagues'

        BottomNavButton:
            id: btn_profil
            icon: 'account'
            text: 'Profile'
'''

class ProfessionalFootballApp(MDApp):
    current_tab = StringProperty('live')
    current_title = StringProperty('Live Matches')
    current_time = StringProperty('')
    
    matches = ListProperty()
    today_matches = ListProperty()
    favorites = ListProperty()
    hidden_matches = ListProperty()
    selected_leagues = ListProperty()
    favorite_leagues = ListProperty()
    country_leagues_map = DictProperty({})
    all_leagues = ListProperty([])
    
    auto_update = BooleanProperty(False)
    update_interval = NumericProperty(600)
    last_update = StringProperty('')
    request_count = NumericProperty(0)
    max_requests = NumericProperty(7500)
    
    current_segment = StringProperty('today')
    
    api_key = StringProperty('ff5507928d7ea3382d5a8149db14e988')
    base_url = StringProperty('https://v3.football.api-sports.io')
    api_available = BooleanProperty(False)

    current_match_goals_for = NumericProperty(0)
    current_match_goals_against = NumericProperty(0)
    
    current_calendar_date = None
    calendar_mode = BooleanProperty(False)
    
    filter_ns_perfect_1_1_enabled = BooleanProperty(False)  
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        self._is_loading = False
        self.leagues = []
        self.leagues_loaded = False
        self._update_event = None

        self.storage = SQLiteStorage()

        self.filtered_matches = []
        self.filter_results = {}
        self._is_filtering = False
        self.filter_condition = self.default_filter_condition
        self._auto_filter_event = None
        self.filter_interval = 600
        self.current_filter = "No Filter"

        self.current_calendar_date = datetime.now().date()
        self.calendar_mode = False
        

        self.team_stats_cache = {}
        self.team_standings_cache = {}
        self.cache_timeout = 300  
    
    def build(self):
        self.theme_cls.primary_palette = 'Blue'
        self.theme_cls.theme_style = 'Light'
        
        self.selected_leagues = [] 

        self.update_time()
        Clock.schedule_interval(self.update_time, 60)
        
        self.load_favorites()
        self.load_hidden_matches()
        self.load_league_selection()
        self.load_favorite_leagues()

        self.load_filter_state()
        
        Clock.schedule_once(lambda dt: self.load_leagues_and_matches(), 0.5)
        
        Clock.schedule_once(lambda dt: self.schedule_auto_filter(), 10)
        
        return Builder.load_string(KV)
    
    def on_stop(self):
        if self._update_event:
            self._update_event.cancel()
            
        if self._auto_filter_event:
            self._auto_filter_event.cancel()
            
        self.save_favorites()
        self.save_hidden_matches()
        self.save_favorite_leagues()
        self.save_league_selection()        
        self.save_filter_state()        
        super().on_stop()

    def filter_out_hidden_matches_immediately(self, matches_list):
        if not matches_list:
            return []
            
        hidden_ids = {m.get('id') for m in self.hidden_matches}
        
        filtered = []
        hidden_count = 0
        
        for match in matches_list:
            match_id = match.get('id')
            
            if match_id in hidden_ids:
                hidden_count += 1
                continue
            
            filtered.append(match)
        
        if hidden_count > 0:
            print(f"🚫 فلترة فورية: تم إزالة {hidden_count} مباراة مخفية")
        
        return filtered
    
    def filter_out_hidden_and_favorite_matches(self, matches_list):
        hidden_ids = {m.get('id') for m in self.hidden_matches}
        favorite_ids = {f.get('id') for f in self.favorites}
        
        filtered = []
        hidden_count = 0
        favorite_count = 0
        
        for match in matches_list:
            match_id = match.get('id')

            if match_id in hidden_ids:
                hidden_count += 1
                continue

            if match_id in favorite_ids:
                favorite_count += 1
                continue
            
            filtered.append(match)
        
        if hidden_count > 0 or favorite_count > 0:
            print(f"🚫 فلترة شاملة: تم إزالة {hidden_count} مخفية و {favorite_count} مفضلة")
        
        return filtered

    def load_filter_state(self):
        self.filter_ns_perfect_1_1_enabled = self.storage.load_filter_state('filter_ns_perfect_1_1_enabled')
            
    def save_filter_state(self):
        self.storage.save_filter_state('filter_ns_perfect_1_1_enabled', self.filter_ns_perfect_1_1_enabled)

    def filter_ns_perfect_1_1(self, match_data):
        try:
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season', datetime.now().year)
            status = match_data.get('status', 'NS')

            if status not in ['NS', 'TBD']:
                return "❌ no (Match already started)"

            if not all([home_team_id, away_team_id, league_id]):
                return "❌ no (Missing team/league data)"

            home_total_goals, home_count = self.fetch_team_last_goals_for_filter(
                home_team_id, league_id, season, is_home_team=True, matches_count=3
            )
            
            away_total_goals, away_count = self.fetch_team_last_goals_for_filter(
                away_team_id, league_id, season, is_home_team=False, matches_count=3
            )

            if home_count < 3 or away_count < 3:
                return f"❌ no (Not enough matches: H:{home_count}, A:{away_count})"

            if home_total_goals == away_total_goals:
                return f"✅ yes (Equal goals: {home_total_goals}-{away_total_goals})"
                
            if home_total_goals > away_total_goals:
                winner_id = home_team_id
                winner_label = "Home"
                winner_goals = home_total_goals
                
                loser_id = away_team_id
                loser_label = "Away"
                loser_goals = away_total_goals
            else:
                winner_id = away_team_id
                winner_label = "Away"
                winner_goals = away_total_goals
                
                loser_id = home_team_id
                loser_label = "Home"
                loser_goals = home_total_goals

            winner_standings = self.fetch_team_standings_for_filter(winner_id, league_id, season)
            loser_standings = self.fetch_team_standings_for_filter(loser_id, league_id, season)
            
            winner_rank = winner_standings.get('current_rank', 'N/A')
            loser_rank = loser_standings.get('current_rank', 'N/A')

            try:
                winner_rank_str = str(winner_rank).strip()
                loser_rank_str = str(loser_rank).strip()

                if not winner_rank_str.isdigit() or not loser_rank_str.isdigit():
                    return f"❌ no (Invalid Rank Format: +:{winner_rank}, -:{loser_rank})"

                winner_rank_int = int(winner_rank_str)
                loser_rank_int = int(loser_rank_str)
                
            except (ValueError, TypeError):
                return f"❌ no (Rank Processing Error: +:{winner_rank}, -:{loser_rank})"

            forbidden_pairs = {
                (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 10), (1, 11), (1, 12),
                (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14),
                (3, 2), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15),
                (4, 2), (4, 3), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (4, 16),
                (5, 2), (5, 3), (5, 4), (5, 6), (5, 7), (5, 8), (5, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16),
                (6, 2), (6, 3), (6, 4), (6, 5), (6, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16),
                (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 8), (7, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (7, 16),
                (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (8, 7), (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16),
                (9, 2), (9, 3), (9, 4), (9, 5), (9, 6), (9, 7), (9, 8), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16),
                (10, 4), (10, 5), (10, 6), (10, 7), (10, 8), (10, 9), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18),
                (11, 4), (11, 6), (11, 7), (11, 8), (11, 9), (11, 10), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18),
                (12, 6), (12, 7), (12, 8), (12, 9), (12, 10), (12, 11), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18),
                (13, 7), (13, 8), (13, 10), (13, 11), (13, 12), (13, 14), (13, 15), (13, 16), (13, 17), (13, 18),
                (14, 8), (14, 9), (14, 10), (14, 11), (14, 12), (14, 13), (14, 15), (14, 16), (14, 17), (14, 18),
                (15, 8), (15, 9), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14),
                (16, 8), (16, 9), (16, 10), (16, 11), (16, 12), (16, 13), (16, 14), (16, 15),
                (17, 15)
            }
            current_pair = (winner_rank_int, loser_rank_int)

            if current_pair in forbidden_pairs:
                return f"❌ no (Forbidden Rank Pair: +{winner_rank_int} vs -{loser_rank_int})"

            goals_diff = winner_goals - loser_goals
            
            return f"✅ yes (+:{winner_label} {winner_goals} | -:{loser_label} {loser_goals} | [+]{winner_rank_int} vs [-]{loser_rank_int} | Diff: +{goals_diff})"
                
        except Exception as e:
            print(f"NS Perfect 1_1 Filter Error: {e}")
            return "❌ no (System Error)"

    def fetch_team_last_goals_for_filter(self, team_id, league_id, season, is_home_team, matches_count=3):
        cache_key = f"goals_{team_id}_{league_id}_{season}_{'home' if is_home_team else 'away'}_last_{matches_count}"
        
        if cache_key in self.team_stats_cache:
            cached_data = self.team_stats_cache[cache_key]
            cached_time = cached_data.get('time', 0)
            if time.time() - cached_time < self.cache_timeout:
                return cached_data['result']
        
        try:
            url = f"{self.base_url}/fixtures"
            params = {
                'team': team_id,
                'league': league_id,
                'season': season,
                'last': 15  
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('response', [])
                
                if not matches:
                    result = (0, 0)
                    self.team_stats_cache[cache_key] = {'result': result, 'time': time.time()}
                    return result
                
                total_goals = 0
                valid_matches = 0
                
                for match in matches:
                    if valid_matches >= matches_count:
                        break
                        
                    fixture = match.get('fixture', {})
                    match_league = match.get('league', {})
                    
                    if (fixture.get('status', {}).get('short') == 'FT' and 
                        match_league.get('id') == league_id):
                        
                        teams = match.get('teams', {})
                        goals = match.get('goals', {})

                        is_current_team_home = teams.get('home', {}).get('id') == team_id
                        
                        if (is_home_team and is_current_team_home) or (not is_home_team and not is_current_team_home):
                            if is_current_team_home:
                                goals_for = goals.get('home', 0)
                            else:
                                goals_for = goals.get('away', 0)
                            
                            total_goals += goals_for
                            valid_matches += 1
                
                result = (total_goals, valid_matches)
                self.team_stats_cache[cache_key] = {'result': result, 'time': time.time()}
                return result
                
            result = (0, 0)
            self.team_stats_cache[cache_key] = {'result': result, 'time': time.time()}
            return result
            
        except Exception as e:
            print(f"Error in fetch_team_last_goals_for_filter for team {team_id}: {e}")
            result = (0, 0)
            self.team_stats_cache[cache_key] = {'result': result, 'time': time.time()}
            return result

    def fetch_team_standings_for_filter(self, team_id, league_id, season):
        cache_key = f"standings_filter_{league_id}_{season}_{team_id}"

        if cache_key in self.team_standings_cache:
            cached_data = self.team_standings_cache[cache_key]
            cached_time = cached_data.get('time', 0)
            if time.time() - cached_time < self.cache_timeout:
                return cached_data['result']
        
        try:
            url = f"{self.base_url}/standings"
            params = {
                'league': league_id,
                'season': season
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                standings = data.get('response', [])
                
                if standings:
                    league_standings = standings[0].get('league', {}).get('standings', [])

                    for standing_group in league_standings:
                        for team_standing in standing_group:
                            if team_standing.get('team', {}).get('id') == team_id:
                                result = {
                                    'current_rank': team_standing.get('rank'),
                                    'points': team_standing.get('points'),
                                    'form': team_standing.get('form')
                                }
                                self.team_standings_cache[cache_key] = {'result': result, 'time': time.time()}
                                return result
                

            result = {'current_rank': 'N/A', 'points': 0, 'form': ''}
            self.team_standings_cache[cache_key] = {'result': result, 'time': time.time()}
            return result
            
        except Exception as e:
            print(f"Error in fetch_team_standings_for_filter: {e}")
            result = {'current_rank': 'N/A', 'points': 0, 'form': ''}
            self.team_standings_cache[cache_key] = {'result': result, 'time': time.time()}
            return result

    def load_favorites(self):
        self.favorites = self.storage.load_favorites()

    def save_favorites(self):
        self.storage.save_favorites(self.favorites)

    def load_hidden_matches(self):
        self.hidden_matches = self.storage.load_hidden_matches()

    def save_hidden_matches(self):
        self.storage.save_hidden_matches(self.hidden_matches)

    def load_league_selection(self):
        self.selected_leagues = self.storage.load_league_selection()

    def save_league_selection(self):
        self.storage.save_league_selection(self.selected_leagues)

    def load_favorite_leagues(self):
        self.favorite_leagues = self.storage.load_favorite_leagues()

    def save_favorite_leagues(self):
        self.storage.save_favorite_leagues(self.favorite_leagues)

    def toggle_filter_ns_perfect_1_1(self):
        self.filter_ns_perfect_1_1_enabled = not self.filter_ns_perfect_1_1_enabled
        self.save_filter_state()
        status = "Enabled" if self.filter_ns_perfect_1_1_enabled else "Disabled"
        self.show_snackbar(f"NS Filter (Perfect 1_1) is now {status}")
        self.show_profile()  

    def on_calendar_date_selected(self, selected_date):
        self.current_calendar_date = selected_date
        self.calendar_mode = True
        
        today = datetime.now().date()
        if selected_date == today:
            self.current_title = "Today's Matches"
        elif selected_date == today + timedelta(days=1):
            self.current_title = "Tomorrow's Matches"
        elif selected_date == today + timedelta(days=2):
            self.current_title = "Day After Tomorrow's Matches"
        else:
            self.current_title = f"Matches for {selected_date.strftime('%d/%m/%Y')}"
        
        print(f"🗓️ تم اختيار التاريخ: {selected_date}")
        self.show_calendar_matches(selected_date)

    def show_calendar_matches(self, target_date):
        self.show_loading(f"Loading scheduled matches for {target_date.strftime('%d/%m/%Y')}...")
        
        def fetch_and_display():
            try:
                matches = self.fetch_matches_by_date_improved(target_date)
                processed_matches = self.process_matches_improved(matches)
                
                Clock.schedule_once(lambda dt: self.display_calendar_matches_improved(processed_matches, target_date), 0)
            except Exception as e:
                print(f"❌ خطأ في جلب المباريات: {e}")
                Clock.schedule_once(lambda dt: self.display_calendar_matches_improved([], target_date), 0)
                
        threading.Thread(target=fetch_and_display, daemon=True).start()

    def fetch_matches_by_date_improved(self, target_date):
        try:
            url = f"{self.base_url}/fixtures"
            date_str = target_date.strftime('%Y-%m-%d')
            params = {'date': date_str}
            
            print(f"🔍 جاري البحث عن المباريات للتاريخ: {date_str}")
            
            response = self.fetch_with_retry(url, params, max_retries=2)
            
            if response and response.status_code == 200:
                data = response.json()
                print(f"📊 الاستجابة من API: {len(data.get('response', []))} مباراة")
                
                if data.get('response'):
                    matches = self.process_api_response_improved(data['response'])

                    matches = self.filter_out_hidden_matches_immediately(matches)
                    
                    print(f"✅ تم العثور على {len(matches)} مباراة (بعد إزالة المخفية)")
                    return matches
                else:
                    print("❌ لا توجد بيانات في الاستجابة")
                    return []
            else:
                print(f"❌ خطأ في API: {response.status_code if response else 'No response'}")
                return []
                
        except Exception as e:
            print(f"❌ خطأ غير متوقع: {e}")
            return []

    def fetch_with_retry(self, url, params, max_retries=2):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                if response.status_code == 200:
                    return response
                else:
                    print(f"⚠️ محاولة {attempt + 1} فشلت: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ محاولة {attempt + 1} فشلت: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(1)
        
        return None

    def process_api_response_improved(self, api_matches):
        processed_matches = []
        
        for match in api_matches:
            try:
                fixture = match.get('fixture', {})
                teams = match.get('teams', {})
                goals = match.get('goals', {})
                league = match.get('league', {})
                
                home_team = teams.get('home', {})
                away_team = teams.get('away', {})
                
                home_team_name = home_team.get('name', 'Home Team')
                away_team_name = away_team.get('name', 'Away Team')
                
                full_home_team_name = home_team.get('name', 'Home Team')
                full_away_team_name = away_team.get('name', 'Away Team')
                
                home_score = goals.get('home')
                away_score = goals.get('away')
                
                status = fixture.get('status', {}).get('short', 'NS')
                elapsed = fixture.get('status', {}).get('elapsed')
                
                processed_match = {
                    'id': fixture.get('id'),
                    'league': league.get('name', 'Unknown League'),
                    'league_id': league.get('id'),
                    'season': league.get('seasons', [{}])[0].get('year', datetime.now().year) if league.get('seasons') else datetime.now().year,
                    'home_team': home_team_name,
                    'full_home_team': full_home_team_name,
                    'home_team_id': home_team.get('id'),
                    'away_team': away_team_name,
                    'full_away_team': full_away_team_name,
                    'away_team_id': away_team.get('id'),
                    'home_score': home_score,
                    'away_score': away_score,
                    'status': status,
                    'elapsed': elapsed,
                    'time': fixture.get('date', ''),
                    'events': match.get('events', []),
                    'venue': fixture.get('venue', {}).get('name', ''),
                    'referee': fixture.get('referee', 'Unknown')
                }
                
                processed_matches.append(processed_match)
                
            except Exception as e:
                print(f"Error processing match: {e}")
                continue
                
        return processed_matches

    def process_matches_improved(self, matches):
        processed = []
        for match in matches:
            try:
                match.setdefault('home_score', None)
                match.setdefault('away_score', None)
                match.setdefault('elapsed', None)
                match.setdefault('events', [])
                
                time_str = match.get('time', '')
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        match['formatted_time'] = dt.strftime('%H:%M')
                    except:
                        match['formatted_time'] = time_str[:16] if time_str else "TBD"
                else:
                    match['formatted_time'] = 'TBD'
                
                processed.append(match)
            except Exception as e:
                print(f"Error in match processing: {e}")
                continue
        return processed

    def get_matches_without_favorites_and_hidden(self, matches_list):
        hidden_ids = {m.get('id') for m in self.hidden_matches}
        
        filtered_list = []
        hidden_count = 0
        
        for match in matches_list:
            match_id = match.get('id')

            if match_id in hidden_ids:
                hidden_count += 1
                continue  
            if self.is_favorite(match_id):
                continue
                
            filtered_list.append(match)
        
        if hidden_count > 0:
            print(f"🚫 تم إزالة {hidden_count} مباراة مخفية نهائيًا ولن تعود")
        
        return filtered_list

    @mainthread
    def display_calendar_matches_improved(self, matches, target_date):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        today = datetime.now().date()
        
        if target_date == today:
            date_label = "📅 TODAY'S SCHEDULED MATCHES"
        elif target_date == today + timedelta(days=1):
            date_label = "📅 TOMORROW'S SCHEDULED MATCHES"
        elif target_date == today + timedelta(days=2):
            date_label = "📅 DAY AFTER TOMORROW'S SCHEDULED MATCHES"
        else:
            date_display = target_date.strftime('%d/%m/%Y')
            date_label = f"📅 SCHEDULED MATCHES ({date_display})"

        header = OneLineListItem(text=date_label)
        header.md_bg_color = get_color_from_hex("#E3F2FD")
        container.add_widget(header)
        
        if matches:
            matches = self.filter_out_hidden_matches_immediately(matches)
            
            required_league_ids = self.get_required_league_ids()
            
            if required_league_ids:
                filtered_matches = [
                    match for match in matches
                    if match.get('league_id') in required_league_ids
                ]
                print(f"🔍 بعد التصفية حسب الدوري: {len(filtered_matches)} مباراة مجدولة")
            else:
                filtered_matches = matches

            final_matches_filtered = []
            if self.filter_ns_perfect_1_1_enabled:
                print(f"🎯 تطبيق فلتر NS Perfect 1_1 على {len(filtered_matches)} مباراة")
                for match in filtered_matches:
                    if match.get('status') == 'NS':  
                        filter_result = self.filter_ns_perfect_1_1(match)
                        if "✅ yes" in filter_result:  
                            final_matches_filtered.append(match)
                            print(f"✅ مباراة تمت تصفيتها: {match.get('home_team')} vs {match.get('away_team')}")
                print(f"🎯 بعد تطبيق فلتر NS Perfect 1_1: {len(final_matches_filtered)} مباراة مجدولة")
            else:
                final_matches_filtered = filtered_matches
                print(f"🎯 فلتر NS Perfect 1_1 غير مفعل، عرض جميع المباريات: {len(final_matches_filtered)}")

            final_matches = self.filter_out_hidden_and_favorite_matches(final_matches_filtered)
            print(f"🚫 النتيجة النهائية: {len(final_matches)} مباراة مجدولة (تم حذف {len(final_matches_filtered) - len(final_matches)} مباراة)")
            
            if final_matches:
                count_label = MDLabel(
                    text=f"Found {len(final_matches)} scheduled matches",
                    font_style='Caption',
                    halign='center',
                    theme_text_color='Secondary',
                    size_hint_y=None,
                    height=dp(25)
                )
                container.add_widget(count_label)
                
                for match in final_matches:
                    item = OptimizedCompactMatchItem(match_data=match)
                    container.add_widget(item)
            else:
                no_matches_text = "No scheduled matches found"
                if required_league_ids:
                    no_matches_text += " with current league filters"
                if self.filter_ns_perfect_1_1_enabled:
                    no_matches_text += " and NS Perfect 1_1 filter"
                self.show_empty_message(no_matches_text)
        else:
            self.show_empty_message(f"No scheduled matches found for {target_date.strftime('%d/%m/%Y')}")

    def show_stats_popup_improved(self, match_data):
        try:
            required_fields = ['home_team_id', 'away_team_id', 'league_id']
            if not all(match_data.get(field) for field in required_fields):
                self.show_snackbar("⚠️ بيانات المباراة غير مكتملة")
                return
                
            popup = StatsPopup()
            popup.home_team_name = match_data.get('full_home_team', match_data.get('home_team', ''))
            popup.away_team_name = match_data.get('full_away_team', match_data.get('away_team', ''))
            
            popup.first_team_goals_for = "0"
            popup.first_team_goals_against = "0"
            popup.second_team_goals_for = "0"
            popup.second_team_goals_against = "0"
            
            from kivy.core.window import Window
            Window.add_widget(popup)
            
            Clock.schedule_once(lambda dt: self.load_popup_statistics_improved(match_data, popup), 0.1)
            
            anim = Animation(opacity=1, duration=0.3)
            anim.start(popup)
            
            Clock.schedule_once(lambda dt: self.close_stats_popup(popup), 30)
        
        except Exception as e:
            print(f"❌ Error showing stats popup: {e}")
            self.show_snackbar("⚠️ خطأ في فتح الإحصائيات")

    def load_popup_statistics_improved(self, match_data, popup):
        try:
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season', datetime.now().year)
            
            if home_team_id and away_team_id and league_id:
                def fetch_stats():
                    try:
                        first_team_role, second_team_role = self.determine_team_order(match_data)
                        
                        if first_team_role == 'home':
                            first_stats = self.fetch_team_last_matches_improved(home_team_id, league_id, season, is_home_team=True)
                            second_stats = self.fetch_team_last_matches_improved(away_team_id, league_id, season, is_home_team=False)
                            first_name_display = popup.home_team_name 
                            second_name_display = popup.away_team_name
                            
                            first_standings = self.fetch_team_standings_improved(home_team_id, league_id, season)
                            second_standings = self.fetch_team_standings_improved(away_team_id, league_id, season)
                        else:
                            first_stats = self.fetch_team_last_matches_improved(away_team_id, league_id, season, is_home_team=False)
                            second_stats = self.fetch_team_last_matches_improved(home_team_id, league_id, season, is_home_team=True)
                            first_name_display = popup.away_team_name
                            second_name_display = popup.home_team_name
                            
                            first_standings = self.fetch_team_standings_improved(away_team_id, league_id, season)
                            second_standings = self.fetch_team_standings_improved(home_team_id, league_id, season)
                        
                        Clock.schedule_once(lambda dt: self.update_popup_stats(
                            popup, first_stats, second_stats, 
                            first_name_display, second_name_display,
                            first_standings, second_standings
                        ), 0)
                        
                    except Exception as e:
                        print(f"❌ خطأ في جلب الإحصائيات: {e}")
                        Clock.schedule_once(lambda dt: self.update_popup_stats(
                            popup, "green:0:0", "green:0:0",
                            popup.home_team_name, popup.away_team_name,
                            None, None
                        ), 0)
                        
                threading.Thread(target=fetch_stats, daemon=True).start()
                
        except Exception as e:
            print(f"❌ خطأ في تحميل الإحصائيات: {e}")

    def fetch_team_last_matches_improved(self, team_id, league_id, season, is_home_team):
        try:
            url = f"{self.base_url}/fixtures"
            params = {
                'team': team_id,
                'league': league_id,
                'season': season,
                'last': 15
            }
            
            response = self.fetch_with_retry(url, params, max_retries=2)
            if not response:
                return "green:0:0"
                
            data = response.json()
            matches = data.get('response', [])
            
            finished_matches = []
            for match in matches:
                fixture = match.get('fixture', {})
                match_league = match.get('league', {})
                
                if (fixture.get('status', {}).get('short') == 'FT' and 
                    match_league.get('id') == league_id):
                    
                    teams = match.get('teams', {})
                    goals = match.get('goals', {})
                    
                    is_current_team_home = teams.get('home', {}).get('id') == team_id
                    
                    match_data = {
                        'home_goals': goals.get('home', 0),
                        'away_goals': goals.get('away', 0),
                        'is_home': is_current_team_home,
                        'date': fixture.get('date', '')
                    }
                    finished_matches.append(match_data)
            
            if not finished_matches:
                return "green:0:0"
                
            finished_matches.sort(key=lambda x: x['date'], reverse=True)
            
            if is_home_team:
                filtered_matches = [m for m in finished_matches if m['is_home']][:3]
                stats = self.calculate_stats(filtered_matches, is_home=True)
            else:
                filtered_matches = [m for m in finished_matches if not m['is_home']][:3]
                stats = self.calculate_stats(filtered_matches, is_home=False)
            
            return stats
            
        except Exception as e:
            print(f"❌ Error in fetch_team_last_matches: {e}")
            return "green:0:0"

    def fetch_team_standings_improved(self, team_id, league_id, season):
        try:
            current_season = season
            last_season = season - 1
            
            current_standings = self._fetch_season_standings(team_id, league_id, current_season)
            last_standings = self._fetch_season_standings(team_id, league_id, last_season)
            
            if not last_standings:
                last_standings = self._find_team_in_all_leagues_last_season(team_id, last_season)
            
            last_rank_display, last_rank_type = self._determine_last_rank_display(last_standings, current_standings)
            
            combined_standings = {
                'current_rank': current_standings.get('current_rank', 'N/A') if current_standings else 'N/A',
                'last_rank': last_rank_display,
                'last_rank_type': last_rank_type,
                'played': current_standings.get('played', 'N/A') if current_standings else 'N/A',
                'current_season': current_season,
                'last_season': last_season
            }
            
            return combined_standings
                
        except Exception as e:
            print(f"Error fetching team standings: {e}")
            return {
                'current_rank': 'N/A',
                'last_rank': 'N/A',
                'last_rank_type': 'normal',
                'played': 'N/A',
                'current_season': season,
                'last_season': season - 1
            }

    def is_hidden(self, match_id):
        return any(m.get('id') == match_id for m in self.hidden_matches)

    def add_hidden_match(self, match):
        if not self.is_hidden(match.get('id')):
            self.hidden_matches.append(match.copy())
            self.save_hidden_matches()
            print(f"✅ تم إضافة المباراة المخفية: {match.get('home_team')} vs {match.get('away_team')}")

    def remove_hidden_match(self, match_id):
        # إزالة المباراة من القائمة في الذاكرة
        self.hidden_matches = [m for m in self.hidden_matches if m.get('id') != match_id]
        # حفظ التغييرات في قاعدة البيانات
        self.save_hidden_matches()
        print(f"🗑️ تم حذف المباراة المخفية {match_id} من قاعدة البيانات")

    def remove_match_from_all_lists(self, match_id):
        self.matches = [m for m in self.matches if m.get('id') != match_id]        
        self.today_matches = [m for m in self.today_matches if m.get('id') != match_id]         
        self.filtered_matches = [m for m in self.filtered_matches if m.get('id') != match_id]
        
        print(f"🗑️ تمت إزالة المباراة {match_id} من جميع القوائم الداخلية")

    def is_favorite(self, match_id):
        return any(f.get('id') == match_id for f in self.favorites)

    def add_favorite(self, match):
        if not self.is_favorite(match.get('id')):
            self.favorites.append(match.copy())
            self.save_favorites()
            if self.current_tab == 'live' and not self.calendar_mode:
                self.show_live_matches()

    def remove_favorite(self, match_id):
        self.favorites = [f for f in self.favorites if f.get('id') != match_id]
        self.save_favorites()
        if self.current_tab == 'live' and not self.calendar_mode:
            self.show_live_matches()
        elif self.current_tab == 'favorites':
            self.show_favorites()

    def is_favorite_league(self, league_id):
        return any(f.get('id') == league_id for f in self.favorite_leagues)

    def add_favorite_league(self, league_name, league_id):
        if not self.is_favorite_league(league_id):
            self.favorite_leagues.append({'name': league_name, 'id': league_id})
            self.save_favorite_leagues()
            self.show_snackbar(f"League added to favorites: {league_name}")

    def remove_favorite_league(self, league_id):
        self.favorite_leagues = [f for f in self.favorite_leagues if f.get('id') != league_id]
        self.save_favorite_leagues()
        self.show_snackbar("League removed from favorites")
        if self.current_tab == 'favorites':
            self.show_favorites()

    def is_league_selected(self, league_id):
        return any(l.get('id') == league_id for l in self.selected_leagues)

    def fetch_leagues(self):
        try:
            url = f"{self.base_url}/leagues"
            params = {'current': 'true'}
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    leagues = []
                    for league in data['response']:
                        league_info = league.get('league', {})
                        country_info = league.get('country', {})
                        
                        league_data = {
                            'id': league_info.get('id'),
                            'name': league_info.get('name'),
                            'type': league_info.get('type'),
                            'logo': league_info.get('logo'),
                            'country_name': country_info.get('name'),
                            'country_code': country_info.get('code'),
                            'flag': country_info.get('flag'),
                            'season': league.get('seasons', [{}])[0].get('year') if league.get('seasons') else None
                        }
                        leagues.append(league_data)
                    
                    return leagues
            return []
        except Exception as e:
            print(f"Error fetching leagues: {e}")
            return []

    def fetch_live_matches_sync(self):
        try:
            url = f"{self.base_url}/fixtures"
            params = {'live': 'all'}
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    matches = self.process_api_response_improved(data['response'])
                    live_matches = [match for match in matches if match.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']]

                    live_matches = self.filter_out_hidden_matches_immediately(live_matches)
                    
                    return live_matches
                else:
                    return []
            else:
                return []
                
        except Exception:
            return []

    def refresh_live_data_loop(self, dt):
        pass
    
    def _fetch_and_update_live_data(self):
        try:
            new_live_matches_data = self.fetch_live_matches_for_update()
            
            if new_live_matches_data:
                self.update_matches_data(new_live_matches_data)
                
            self.last_update = datetime.now().strftime('%H:%M:%S')
            
        except Exception as e:
            print(f"Error in auto-update: {e}")
            self.show_snackbar(f"Auto update error: {e}", duration=4)
            
    def fetch_live_matches_for_update(self):
        try:
            url = f"{self.base_url}/fixtures"
            params = {'live': 'all'}
            
            response = self.fetch_with_retry(url, params, max_retries=1)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    matches = self.process_api_response_improved(data['response'])
                    live_matches = [match for match in matches if match.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']]

                    live_matches = self.filter_out_hidden_matches_immediately(live_matches)
                    
                    return live_matches
            return []
                
        except Exception:
            return []

    @mainthread
    def update_matches_data(self, new_matches):
        hidden_ids = {m.get('id') for m in self.hidden_matches}

        filtered_new_matches = [
            match for match in new_matches 
            if match.get('id') not in hidden_ids
        ]
        
        print(f"🔄 تحديث البيانات: {len(new_matches)} مباراة جديدة، {len(new_matches) - len(filtered_new_matches)} مخفية")
        
        new_matches_dict = {m.get('id'): m for m in filtered_new_matches}
        
        updated_self_matches = []
        should_refresh_ui = False
        
        for old_match in self.matches:
            match_id = old_match.get('id')

            if match_id in hidden_ids:
                continue
                
            new_match = new_matches_dict.pop(match_id, None)
            
            if new_match:
                old_status = old_match.get('status')
                new_status = new_match.get('status')
                
                old_match.update(new_match)
                self.find_and_update_match_widget(old_match)
                
                updated_self_matches.append(old_match)
                
                if old_status in ['1H', '2H', 'HT', 'LIVE'] and new_status in ['FT', 'AET', 'PEN']:
                    should_refresh_ui = True
            else:
                updated_self_matches.append(old_match)

        for new_match_id, new_match in new_matches_dict.items():
            if new_match_id not in hidden_ids:
                updated_self_matches.append(new_match)
                should_refresh_ui = True
        
        self.matches = updated_self_matches
        self.today_matches = [m for m in self.matches if self._is_today(m.get('time'))]

        if should_refresh_ui and self.current_tab == 'live' and not self.calendar_mode:
            if self.current_filter != "No Filter":
                 self.run_filter_process_threaded() 
            else:
                 self.show_live_matches()
        
        self.root.ids.topbar.right_action_items[0][0] = 'update'
        Clock.schedule_once(lambda dt: self._reset_update_icon(), 2)
        
    def _reset_update_icon(self):
        self.root.ids.topbar.right_action_items[0][0] = 'autorenew'

    def find_and_update_match_widget(self, match_data):
        match_id = match_data.get('id')
        main_list = self.root.ids.main_list
        
        for widget in main_list.children:
            if isinstance(widget, OptimizedCompactMatchItem) and widget.match_data.get('id') == match_id:
                widget.match_data = match_data.copy()
                break

    def _is_today(self, time_str):
        if not time_str:
            return False
        try:
            match_date = datetime.fromisoformat(time_str.replace('Z', '+00:00')).date()
            return match_date == datetime.now().date()
        except:
            return False

    def get_required_league_ids(self):
        selected_league_ids = {l.get('id') for l in self.selected_leagues}
        favorite_league_ids = {l.get('id') for l in self.favorite_leagues}
        return selected_league_ids | favorite_league_ids

    def calcul(self, matches, is_home):
        try:
            if not matches:
                return "green:0:0"
            
            total_goals_for = 0
            total_goals_against = 0
            zero_goal_matches = 0
            
            for match in matches:
                if is_home:
                    goals_for = match.get('home_goals', 0)
                    goals_against = match.get('away_goals', 0)
                else:
                    goals_for = match.get('away_goals', 0)
                    goals_against = match.get('home_goals', 0)
                
                total_goals_for += goals_for
                total_goals_against += goals_against
                
                if goals_for == 0:
                    zero_goal_matches += 1
            
            final_goals_for = min(total_goals_for, 9)
            final_goals_against = min(total_goals_against, 9)

            if final_goals_for >= 6:
                if zero_goal_matches == 0:
                    return "green:" + str(final_goals_for) + ":" + str(final_goals_against)
                elif zero_goal_matches == 1:
                    return "blue:" + str(final_goals_for) + ":" + str(final_goals_against)
                elif zero_goal_matches >= 2:
                    return "red:" + str(final_goals_for) + ":" + str(final_goals_against)
            else:
                return "green:" + str(final_goals_for) + ":" + str(final_goals_against)
                
        except Exception as e:
            print(f"Error in calcul: {e}")
            return "green:0:0"

    def calculate_stats(self, matches, is_home):
        try:
            result = self.calcul(matches, is_home)
            
            if ":" in result:
                parts = result.split(":")
                if len(parts) == 3:
                    return result
            
            return "green:0:0"
            
        except Exception as e:
            print(f"Error in calculate_stats: {e}")
            return "green:0:0"

    def _determine_last_rank_display(self, last_standings, current_standings):
        if not last_standings:
            return "N/A", "normal"
        
        last_rank = last_standings.get('current_rank', 'N/A')
        last_league = last_standings.get('league_name', '')
        current_league = current_standings.get('league_name', '') if current_standings else ''
        
        if last_league == current_league:
            return str(last_rank), "normal"
        
        if last_rank == 'N/A':
            return "NEW", "new_team"
        
        if last_league != current_league:
            try:
                rank_int = int(last_rank)
                if 1 <= rank_int <= 6:
                    return f"↑{last_rank}", "promoted_green"
                elif 6 < rank_int <= 20:
                    return f"↓{last_rank}", "relegated_red"
                else:
                    return str(last_rank), "normal"
            except:
                return str(last_rank), "normal"
        
        return str(last_rank), "normal"

    def _find_team_in_all_leagues_last_season(self, team_id, last_season):
        try:
            url = f"{self.base_url}/leagues"
            params = {
                'team': team_id,
                'season': last_season
            }
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    for league_data in data['response']:
                        league_info = league_data.get('league', {})
                        league_id = league_info.get('id')
                        league_name = league_info.get('name', '')
                        
                        standings = self._fetch_season_standings(team_id, league_id, last_season)
                        if standings:
                            standings['league_name'] = league_name
                            return standings
            
            return None
            
        except Exception as e:
            print(f"Error finding team in all leagues: {e}")
            return None

    def _fetch_season_standings(self, team_id, league_id, season):
        try:
            url = f"{self.base_url}/standings"
            params = {
                'league': league_id,
                'season': season,
                'team': team_id
            }
            
            response = self.fetch_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                
                if data.get('response'):
                    standings_data = data['response'][0]
                    league_standings = standings_data.get('league', {}).get('standings', [])
                    league_name = standings_data.get('league', {}).get('name', '')
                    
                    if league_standings and len(league_standings) > 0:
                        for standing_group in league_standings:
                            for team_standing in standing_group:
                                if team_standing.get('team', {}).get('id') == team_id:
                                    current_rank = team_standing.get('rank', 'N/A')
                                    points = team_standing.get('points', 'N/A')
                                    played = team_standing.get('all', {}).get('played', 'N/A')
                                    
                                    standings_info = {
                                        'current_rank': str(current_rank),
                                        'points': str(points),
                                        'played': str(played),
                                        'won': team_standing.get('all', {}).get('win'),
                                        'draw': team_standing.get('all', {}).get('draw'),
                                        'lost': team_standing.get('all', {}).get('lose'),
                                        'season': season,
                                        'league_name': league_name
                                    }
                                    
                                    return standings_info
            
            return None
            
        except Exception as e:
            print(f"Error fetching season standings: {e}")
            return None

    def determine_team_order(self, match_data):
        home_score = match_data.get('home_score')
        away_score = match_data.get('away_score')
        status = match_data.get('status', 'NS')
        
        home_score = home_score if home_score is not None else 0
        away_score = away_score if away_score is not None else 0
        
        if (home_score == 0 and away_score == 0) or status == 'NS':
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season', datetime.now().year)
            
            if home_team_id and away_team_id and league_id:
                home_stats = self.fetch_team_last_matches_improved(home_team_id, league_id, season, is_home_team=True)
                away_stats = self.fetch_team_last_matches_improved(away_team_id, league_id, season, is_home_team=False)
                
                home_goals_for = int(home_stats.split(':')[1]) if home_stats and ":" in home_stats else 0
                away_goals_for = int(away_stats.split(':')[1]) if away_stats and ":" in away_stats else 0
                
                if home_goals_for >= away_goals_for:
                    return 'home', 'away'
                else:
                    return 'away', 'home'
        
        if home_score < away_score:
            return 'home', 'away'
        elif away_score < home_score:
            return 'away', 'home'
        else:
            return 'home', 'away'

    @mainthread
    def update_popup_stats(self, popup, first_stats, second_stats, first_name_display, second_name_display, first_standings=None, second_standings=None):
        try:
            popup.first_team_name_display = first_name_display
            popup.second_team_name_display = second_name_display
            
            def extract_goals_and_color(stats):
                if stats and ":" in stats:
                    parts = stats.split(":")
                    if len(parts) == 3:
                        return parts[0], parts[1], parts[2]
                return "green", "0", "0"
            
            first_color, first_for, first_against = extract_goals_and_color(first_stats)
            popup.first_team_color = first_color
            popup.first_team_goals_for = first_for
            popup.first_team_goals_against = first_against
            
            second_color, second_for, second_against = extract_goals_and_color(second_stats)
            popup.second_team_color = second_color
            popup.second_team_goals_for = second_for
            popup.second_team_goals_against = second_against
            
            if first_standings:
                popup.first_team_current_rank = first_standings.get('current_rank', 'N/A')
                popup.first_team_last_rank = first_standings.get('last_rank', 'N/A')
                popup.first_team_points = first_standings.get('points', 'N/A')
                popup.first_team_played = first_standings.get('played', 'N/A')
            else:
                popup.first_team_current_rank = 'N/A'
                popup.first_team_last_rank = 'N/A'
                popup.first_team_points = 'N/A'
                popup.first_team_played = 'N/A'
            
            if second_standings:
                popup.second_team_current_rank = second_standings.get('current_rank', 'N/A')
                popup.second_team_last_rank = second_standings.get('last_rank', 'N/A')
                popup.second_team_points = second_standings.get('points', 'N/A')
                popup.second_team_played = second_standings.get('played', 'N/A')
            else:
                popup.second_team_current_rank = 'N/A'
                popup.second_team_last_rank = 'N/A'
                popup.second_team_points = 'N/A'
                popup.second_team_played = 'N/A'
                
        except Exception as e:
            print(f"Error updating popup stats: {e}")

    def close_stats_popup(self, popup):
        anim = Animation(opacity=0, duration=0.3)
        anim.start(popup)
        Clock.schedule_once(lambda dt: self.root.ids.stats_popup_container.remove_widget(popup), 0.3)

    @mainthread
    def update_ui_with_matches(self, matches):
        try:
            filtered_matches = self.filter_out_hidden_and_favorite_matches(matches)
            
            self.matches = filtered_matches
            self.today_matches = [m for m in filtered_matches if self._is_today(m.get('time'))]
            self.api_available = True
            
            if self.current_tab == 'live' and not self.calendar_mode:
                pass 
                    
            self.show_snackbar(f"Loaded {len(filtered_matches)} live matches")
            
        except Exception:
            pass

    @mainthread
    def show_error_in_main_thread(self, error_msg):
        self.show_api_error(error_msg)

    @mainthread
    def show_no_matches_in_main_thread(self):
        self.show_no_live_matches()

    def show_loading(self, message="Loading...", progress=0, status=""):
        container = self.root.ids.main_list
        container.clear_widgets()
        loading_widget = LoadingWidget()
        loading_widget.loading_text = message
        loading_widget.progress_value = progress
        loading_widget.status_text = status if status else "Please wait..."
        container.add_widget(loading_widget)

    def show_api_error(self, error_msg=""):
        self.api_available = False
        container = self.root.ids.main_list
        container.clear_widgets()
        error_widget = ErrorWidget()
        error_widget.error_text = f"Error: {error_msg}" if error_msg else "Connection error"
        container.add_widget(error_widget)

    def show_no_live_matches(self):
        self.api_available = True
        container = self.root.ids.main_list
        container.clear_widgets()
        
        empty_item = TwoLineListItem(
            text="No live matches",
            secondary_text="No matches are currently live. Try again later.",
            theme_text_color='Secondary'
        )
        container.add_widget(empty_item)

    def organize_live_matches_by_minute(self, live_matches):
        if not live_matches:
            return []
        
        matches_by_minute = {}
        
        for match in live_matches:
            elapsed = match.get('elapsed', 0)
            status = match.get('status', '')
            
            if status in ['1H', '2H', 'LIVE']:
                if elapsed is not None:
                    if elapsed <= 15:
                        minute_group = '1-15'
                    elif elapsed <= 30:
                        minute_group = '16-30'
                    elif elapsed <= 45:
                        minute_group = '31-45'
                    elif elapsed <= 60:
                        minute_group = '46-60'
                    elif elapsed <= 75:
                        minute_group = '61-75'
                    else:
                        minute_group = '76+'
                else:
                    minute_group = 'LIVE'
            elif status == 'HT':
                minute_group = 'HT'
            elif status == 'ET':
                minute_group = 'ET'
            elif status == 'P':
                minute_group = 'PEN'
            else:
                minute_group = 'OTHER'
        
            if minute_group not in matches_by_minute:
                matches_by_minute[minute_group] = []
            matches_by_minute[minute_group].append(match)
        
        group_order = [
            '76+', '61-75', '46-60', 'HT', '31-45', '16-30', '1-15', 
            'ET', 'PEN', 'LIVE', 'OTHER' 
        ]
        
        organized_matches = []
        for group in group_order:
            if group in matches_by_minute:
                matches_by_minute[group].sort(key=lambda m: m.get('elapsed', 0), reverse=False)
                organized_matches.extend(matches_by_minute[group])
        
        return organized_matches

    def show_live_matches(self):
        if self.calendar_mode:
            return
            
        if not self.api_available:
            self.show_api_error()
            return
            
        container = self.root.ids.main_list
        container.clear_widgets()
        
        if self.current_filter != "No Filter" and self.filtered_matches:
            self.display_filtered_matches()
            return
            
        live_matches = [m for m in self.matches if m.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']]
        
        required_league_ids = self.get_required_league_ids()
        
        if required_league_ids:
            filtered_live_matches = [
                match for match in live_matches
                if match.get('league_id') in required_league_ids
            ]
        else:
            filtered_live_matches = live_matches

        final_matches_to_show = self.filter_out_hidden_and_favorite_matches(filtered_live_matches)
        print(f"📊 Live Matches: {len(live_matches)} -> {len(filtered_live_matches)} بعد فلترة الدوريات -> {len(final_matches_to_show)} بعد الإخفاء النهائي")
        
        organized_live_matches = self.organize_live_matches_by_minute(final_matches_to_show)

        if len(organized_live_matches) > 0:
            count_label = MDLabel(
                text=f"Live Matches: {len(organized_live_matches)}",
                font_style='Button',
                halign='center',
                theme_text_color='Primary',
                bold=True,
                size_hint_y=None,
                height=dp(30)
            )
            container.add_widget(count_label)
            
            filter_texts = []
            if len(self.selected_leagues) > 0:
                filter_texts.append(f"Selected: {len(self.selected_leagues)}")
            if len(self.favorite_leagues) > 0:
                 filter_texts.append(f"Favorites: {len(self.favorite_leagues)}")
                
            if required_league_ids:
                filter_info = MDLabel(
                    text=f"Leagues Filter (Active): { ' | '.join(filter_texts) }",
                    font_style='Caption',
                    halign='center',
                    theme_text_color='Secondary',
                    size_hint_y=None,
                    height=dp(20)
                )
                container.add_widget(filter_info)
            
            if organized_live_matches:
                live_header = OneLineListItem(text=f"🔴 LIVE MATCHES ({len(organized_live_matches)})")
                live_header.md_bg_color = get_color_from_hex("#FFEBEE")
                container.add_widget(live_header)
                
                for match in organized_live_matches:
                    item = OptimizedCompactMatchItem(
                        match_data=match, 
                        is_fav=self.is_favorite(match.get('id'))
                    )
                    container.add_widget(item)
            
            if not organized_live_matches:
                self.show_empty_message("No live matches currently")
        else:
            self.show_empty_message("No live matches currently")

    def populate_matches(self, matches_list, container):
        for match in matches_list:
            item = OptimizedCompactMatchItem(
                match_data=match, 
                is_fav=self.is_favorite(match.get('id'))
            )
            container.add_widget(item)

    def show_favorites(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        all_available_matches = list({m['id']: m for m in self.matches + self.today_matches}.values())

        fav_matches_data = [m for m in all_available_matches 
                           if self.is_favorite(m.get('id')) and not self.is_hidden(m.get('id'))]
        
        fav_leagues_data = self.favorite_leagues
        
        has_favorites = len(fav_matches_data) > 0 or len(fav_leagues_data) > 0
        
        if has_favorites:
            if fav_matches_data:
                matches_header = OneLineListItem(text="⭐ FAVORITE MATCHES")
                matches_header.md_bg_color = get_color_from_hex("#FFF8E1")
                container.add_widget(matches_header)
                self.populate_matches(fav_matches_data, container)
            
            if fav_leagues_data:
                leagues_header = OneLineListItem(text="🏆 FAVORITE LEAGUES")
                leagues_header.md_bg_color = get_color_from_hex("#E8F5E8")
                container.add_widget(leagues_header)
                
                for league in fav_leagues_data:
                    item = FavoriteLeagueItem(
                        league_name=league['name'],
                        league_id=league['id']
                    )
                    container.add_widget(item)
        else:
            self.show_empty_message("No favorites")

    def show_empty_message(self, message):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        empty_item = TwoLineListItem(
            text=message,
            secondary_text="Please check other tabs or refresh.",
            theme_text_color='Secondary'
        )
        container.add_widget(empty_item)

    def update_time(self, *args):
        now = datetime.now()
        self.current_time = now.strftime('%H:%M - %d/%m/%Y')

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.update_nav_buttons()

        if tab_name == 'live':
            self.current_title = 'Live Matches'
            self.calendar_mode = False
            self.show_live_matches()
        elif tab_name == 'favorites':
            self.current_title = 'My Favorites'
            self.calendar_mode = False
            self.show_favorites()
        elif tab_name == 'leagues':
            self.current_title = 'Leagues'
            self.calendar_mode = False
            self.show_leagues()
        elif tab_name == 'profile':
            self.current_title = 'My Profile'
            self.calendar_mode = False
            self.show_profile()

    def update_nav_buttons(self):
        tabs = {
            'live': 'btn_en_cours',
            'favorites': 'btn_favoris',
            'leagues': 'btn_competitions',
            'profile': 'btn_profil'
        }
        for tab_name, btn_id in tabs.items():
            self.root.ids[btn_id].selected = (tab_name == self.current_tab)

    def show_leagues(self):
        c = self.root.ids.main_list
        c.clear_widgets()

        box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=6)
        self.search_input = MDTextField(
            hint_text="Search for a league (ex: premier league, serie a)",
            size_hint_x=0.8
        )
        search_btn = MDFlatButton(
            text="Search",
            on_release=lambda x: self.fetch_leagues_threaded(self.search_input.text.strip().lower())
        )
        box.add_widget(self.search_input)
        box.add_widget(search_btn)
        c.add_widget(box)

        control_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=6)
        
        save_btn = MDRaisedButton(
            text="Save Selection",
            on_release=lambda x: self.save_selected_leagues(),
            size_hint_x=0.5
        )
        
        supreme_btn = MDRaisedButton(
            text="Supreme", 
            on_release=lambda x: self.save_supreme_selection(),
            size_hint_x=0.5,
            md_bg_color=get_color_from_hex("#000000")
        )
        
        control_box.add_widget(save_btn)
        control_box.add_widget(supreme_btn)
        c.add_widget(control_box)

        self.competitions_layout = MDGridLayout(cols=1, adaptive_height=True, spacing=10, padding=6)
        c.add_widget(self.competitions_layout)

        Clock.schedule_once(lambda dt: self.display_saved_leagues_for_selection(), 0.1)

    def display_saved_leagues_for_selection(self):
        layout = self.competitions_layout
        layout.clear_widgets()
        
        if not self.all_leagues:
            layout.add_widget(OneLineListItem(text="Please wait, loading leagues..."))
            return
            
        layout.add_widget(OneLineListItem(text="📋 PREVIOUSLY SELECTED LEAGUES"))
        
        current_selected_ids = {l.get('id') for l in self.selected_leagues}
        
        selected_leagues_info = [
            (f"{l['name']} ({l.get('country_name', 'World')})", l['id']) 
            for l in self.all_leagues if l['id'] in current_selected_ids
        ]

        if not selected_leagues_info:
             layout.add_widget(OneLineListItem(text="No leagues selected."))
             return

        for name, lid in selected_leagues_info:
            item = LeagueItem(league_name=name, league_id=lid)
            item.selected = True
            item.ids.check.icon = "checkbox-marked"
            layout.add_widget(item)

    def save_supreme_selection(self):
        layout = getattr(self, 'competitions_layout', None)
        if not layout:
            self.show_snackbar("⚠️ Interface error (Leagues)")
            return

        leagues_in_ui = [child for child in layout.children if isinstance(child, LeagueItem)]
        
        newly_selected_leagues_data = []
        deselected_leagues_ids = []
        
        for item in leagues_in_ui:
            if item.selected:
                league_data = {
                    'name': item.text,
                    'id': item.league_id
                }
                newly_selected_leagues_data.append(league_data)
            else:
                deselected_leagues_ids.append(item.league_id)

        current_selected = [l for l in self.selected_leagues if l['id'] not in deselected_leagues_ids]
        
        current_ids = {l['id'] for l in current_selected}
        
        for league in newly_selected_leagues_data:
            if league['id'] not in current_ids:
                current_selected.append(league)
                
        self.selected_leagues = current_selected
        self.save_league_selection()  
        message = f"✅ Supreme update successful: {len(self.selected_leagues)} leagues kept. (Removed: {len(deselected_leagues_ids)})"
        self.show_dialog(message)
        
        if self.current_tab == 'live':
            self.show_live_matches()
        
        self.display_saved_leagues_for_selection()

    def show_profile(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        profile_header = OneLineListItem(text="👤 MY PROFILE")
        profile_header.md_bg_color = get_color_from_hex("#E8F5E8")
        container.add_widget(profile_header)
        
        stats_box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(120))
        
        matches_count = len(self.favorites)
        leagues_count = len(self.favorite_leagues)
        hidden_count = len(self.hidden_matches)
        
        stats_box.add_widget(MDLabel(
            text=f"Favorite matches: {matches_count}",
            theme_text_color='Primary',
            halign='center'
        ))
        stats_box.add_widget(MDLabel(
            text=f"Favorite leagues: {leagues_count}",
            theme_text_color='Primary', 
            halign='center'
        ))
        stats_box.add_widget(MDLabel(
            text=f"Hidden matches: {hidden_count}",
            theme_text_color='Primary',
            halign='center'
        ))
        
        container.add_widget(stats_box)
        
        filter_header = OneLineListItem(text="🎯 ADVANCED FILTER SYSTEM")
        filter_header.md_bg_color = get_color_from_hex("#E1F5FE")
        container.add_widget(filter_header)
        
        filter_buttons_box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(250))
        
        btn_condition1 = MDRaisedButton(
            text="🔍 Condition 1: One Team Scored/No Goals",
            on_release=lambda x: self.apply_filter_condition_1(),
            size_hint_y=None,
            height=dp(40)
        )
        filter_buttons_box.add_widget(btn_condition1)
        
        btn_condition2 = MDRaisedButton(
            text="🎯 Condition 2: Loser Scored More (Last 3)",
            on_release=lambda x: self.apply_filter_condition_2(),
            size_hint_y=None,
            height=dp(40)
        )
        filter_buttons_box.add_widget(btn_condition2)
        
        btn_combined_1_2 = MDRaisedButton(
            text="⭐ المطلوب: شرط (1) + شرط (2) ⭐",
            on_release=lambda x: self.apply_combined_filter_1_and_2(),
            size_hint_y=None,
            height=dp(40),
            md_bg_color=get_color_from_hex("#00A0B0")
        )
        filter_buttons_box.add_widget(btn_combined_1_2)

        btn_ns_filter = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            padding=dp(5),
            spacing=dp(10)
        )
        btn_ns_filter_label = MDLabel(
            text="📅 NS Filter (Perfect 1_1) for Calendar",
            theme_text_color='Primary',
            halign='left',
            valign='center',
            size_hint_x=0.8
        )
        btn_ns_filter_icon = MDIconButton(
            icon= "checkbox-marked" if self.filter_ns_perfect_1_1_enabled else "checkbox-blank-outline",
            theme_text_color='Custom',
            text_color=get_color_from_hex("#4CAF50") if self.filter_ns_perfect_1_1_enabled else get_color_from_hex("#F44336"),
            on_release=lambda x: self.toggle_filter_ns_perfect_1_1(),
            size_hint_x=0.2
        )
        btn_ns_filter.add_widget(btn_ns_filter_label)
        btn_ns_filter.add_widget(btn_ns_filter_icon)
        filter_buttons_box.add_widget(btn_ns_filter)
        
        btn_reset = MDFlatButton(
            text="🔄 Reset Filter",
            on_release=lambda x: self.reset_filter_ui(),
            size_hint_y=None,
            height=dp(40)
        )
        filter_buttons_box.add_widget(btn_reset)
        
        container.add_widget(filter_buttons_box)
        
        settings_header = OneLineListItem(text="⚙️ SETTINGS")
        settings_header.md_bg_color = get_color_from_hex("#F3E5F5")
        container.add_widget(settings_header)
        
        hidden_matches_btn = OneLineIconListItem(
            text="👻 Manage Hidden Matches",
            on_release=lambda x: self.show_hidden_matches(),
            bg_color=get_color_from_hex("#FFFFFF")
        )
        container.add_widget(hidden_matches_btn)
        
        info_header = OneLineListItem(text="ℹ️ ABOUT")
        info_header.md_bg_color = get_color_from_hex("#E3F2FD")
        container.add_widget(info_header)
        
        container.add_widget(OneLineListItem(text="📱 Version: 1.0.0"))
        container.add_widget(OneLineListItem(text="⚽ Football Live App"))
        container.add_widget(OneLineListItem(text="👨‍💻 Developed with KivyMD"))

    def show_hidden_matches(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        if self.hidden_matches:
            header = OneLineListItem(text="👻 HIDDEN MATCHES")
            header.md_bg_color = get_color_from_hex("#F3E5F5")
            container.add_widget(header)
            
            for match in self.hidden_matches:
                item = OptimizedCompactMatchItem(
                    match_data=match, 
                    is_fav=self.is_favorite(match.get('id'))
                )
                container.add_widget(item)
            
            clear_btn = MDRaisedButton(
                text="Clear All Hidden Matches",
                pos_hint={'center_x': 0.5},
                size_hint_x=0.8,
                on_release=lambda x: self.clear_all_hidden_matches()
            )
            container.add_widget(clear_btn)
        else:
            self.show_empty_message("No hidden matches")

    def clear_all_hidden_matches(self):
        if self.hidden_matches:
            self.hidden_matches = []
            self.save_hidden_matches()  # هذا مهم لحفظ التغيير في قاعدة البيانات
            self.show_snackbar("All hidden matches cleared permanently")
            
            # تحديث الواجهة
            if self.current_tab == 'profile':
                self.show_hidden_matches()
        else:
            self.show_snackbar("No hidden matches to clear")

    def fetch_leagues_threaded(self, keyword=""):
        t = threading.Thread(target=self.fetch_leagues_api, args=(keyword,))
        t.start()

    def fetch_leagues_api(self, keyword=""):
        url = "https://v3.football.api-sports.io/leagues"
        headers = {"x-apisports-key": "ff5507928d7ea3382d5a8149db14e988"}
        try:
            if self.leagues_loaded:
                 leagues = self.all_leagues
            else:
                resp = requests.get(url, headers=headers)
                data = resp.json()
                leagues = data.get("response", [])
            
            filtered = []

            for item in leagues:
                if isinstance(item, dict) and 'league' in item:
                    league = item.get("league", {})
                    country = item.get("country", {})
                else:
                    league = item
                    country = {'name': item.get('country_name', ''), 'code': item.get('country_code', '')}

                name = league.get("name", "")
                country_name = country.get("name", "")
                league_id = league.get("id", "")
                lname = name.lower()
                cname = country_name.lower()

                if keyword and keyword not in lname and keyword not in cname:
                    continue
                if any(x in lname for x in ["women", "feminine", "u19", "u20", "u17"]):
                    continue

                filtered.append((f"{name} ({country_name})", league_id))

            Clock.schedule_once(lambda dt: self.display_leagues(filtered))
        except Exception as e:
            print("⚠️ Loading error:", e)
            Clock.schedule_once(lambda dt: self.show_dialog("Error loading leagues"))

    def display_leagues(self, leagues_list):
        layout = self.competitions_layout
        layout.clear_widgets()

        if not leagues_list:
            layout.add_widget(OneLineListItem(text="No leagues found"))
            return

        layout.add_widget(OneLineListItem(text="📋 SEARCH RESULTS"))
        
        current_selected_ids = {l.get('id') for l in self.selected_leagues}
        
        for name, lid in leagues_list:
            item = LeagueItem(league_name=name, league_id=lid)
            
            if lid in current_selected_ids:
                item.selected = True
                item.ids.check.icon = "checkbox-marked"
            
            layout.add_widget(item)

    def save_selected_leagues(self):
        selected = []
        layout = getattr(self, 'competitions_layout', None)
        
        if layout:
            for child in layout.children:
                if isinstance(child, LeagueItem) and hasattr(child, 'selected') and child.selected:
                    selected.append({
                        'name': child.text,
                        'id': child.league_id
                    })

        if selected:
            old_data = self.selected_leagues.copy()

            merged = {item['id']: item for item in old_data}
            for league in selected:
                merged[league['id']] = league

            final_list = list(merged.values())

            self.selected_leagues = final_list
            self.save_league_selection()

            message = f"✅ {len(selected)} new leagues added! (Total: {len(final_list)})"
        else:
            message = "⚠️ No leagues selected"
        
        self.show_dialog(message)
        
        if self.current_tab == 'live':
            self.show_live_matches()

    def show_snackbar(self, message, duration=3):
        try:
            Snackbar(
                text=message,
                duration=duration,
                snackbar_x="10dp",
                snackbar_y="10dp",
                size_hint_x=(Window.width - (dp(10) * 2)) / Window.width,
                bg_color=get_color_from_hex("#323232")
            ).open()
        except Exception as e:
            print(f"Error showing snackbar: {e}")

    def show_dialog(self, text):
        self.dialog = MDDialog(
            title="Information",
            text=text,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: self.dialog.dismiss())]
        )
        self.dialog.open()

    def open_menu(self):
        self.show_snackbar('Menu opened')

    def go_back(self):
        if self.calendar_mode:
            self.calendar_mode = False
            self.current_title = 'Live Matches'
            self.show_live_matches()
            self.show_snackbar('Back to live matches')
        else:
            self.show_snackbar('Back')

    def manual_refresh(self):
        self.refresh_data()
        self.show_snackbar('Manual refresh...')

    def toggle_auto_update(self):
        self.auto_update = not self.auto_update
        status = "enabled" if self.auto_update else "disabled"
        self.show_snackbar(f"Auto update {status}")
        
        if self.auto_update:
            if not self._update_event:
                self._update_event = Clock.schedule_interval(self.refresh_live_data_loop, self.update_interval)
            elif not self._update_event.is_active:
                self._update_event()
        else:
            if self._update_event:
                self._update_event.cancel()

    def show_hidden_matches_in_profile(self):
        if self.current_tab == 'profile':
            self.show_profile()

    def retry_loading(self):
        self.load_leagues_and_matches()

    def refresh_data(self):
        threading.Thread(target=self._fetch_and_update_live_data, daemon=True).start()

    def default_filter_condition(self, match_data):
        return "❌ no"

    def filter_condition_1(self, match_data):
        try:
            home_score = match_data.get('home_score', 0)
            away_score = match_data.get('away_score', 0)
            status = match_data.get('status', '')
            
            if status not in ['NS', '1H', '2H', 'HT', 'ET', 'LIVE']:
                 return "❌ no"
            
            if status == 'NS':
                return "✅ yes"
            
            if (home_score > 0 and away_score == 0) or (home_score == 0 and away_score > 0):
                return "✅ yes"
            
            if home_score == 0 and away_score == 0:
                return "✅ yes"
            
            return "❌ no"
        except Exception as e:
            print(f"Error in filter_condition_1: {e}")
            return "❌ no"

    def extract_goals_for_and_against(self, stats_str):
        try:
            parts = stats_str.split(":")
            if len(parts) == 3:
                goals_for = int(parts[1]) if parts[1].isdigit() else 0
                goals_against = int(parts[2]) if parts[2].isdigit() else 0
                return goals_for, goals_against
            return 0, 0
        except:
            return 0, 0

    def filter_condition_2(self, match_data):
        try:
            home_team_id = match_data.get('home_team_id')
            away_team_id = match_data.get('away_team_id')
            league_id = match_data.get('league_id')
            season = match_data.get('season', datetime.now().year)
            home_score = match_data.get('home_score', 0)
            away_score = match_data.get('away_score', 0)
            status = match_data.get('status', 'NS')
            
            # ------------------------------------------------------------------

            if status in ['FT', 'AET', 'PEN']:

                if home_score == 0 and away_score == 0:
                    return "❌ no (انتهت بالتعادل السلبي 0-0)"
                

                return "❌ no (انتهت: FT/AET/PEN)"

            # ------------------------------------------------------------------

            if home_score > 0 and away_score > 0:
                return "❌ no (سجلوا كلاهما)"

            # ------------------------------------------------------------------

            if status not in ['NS', '1H', '2H', 'HT', 'ET', 'LIVE']:
                return "❌ no"


            if home_score == away_score and status != 'NS': 
                return "✅ yes" 
            

            if status == 'NS':
                return "✅ yes"
                

            if not home_team_id or not away_team_id or not league_id:
                return "❌ no"


            if home_score < away_score:
                losing_team_id = home_team_id
                winning_team_id = away_team_id
                losing_is_home = True
            else: 
                losing_team_id = away_team_id
                winning_team_id = home_team_id
                losing_is_home = False
            

            losing_stats_str = self.fetch_team_last_matches_improved(
                losing_team_id, league_id, season, losing_is_home
            )
            
            winning_stats_str = self.fetch_team_last_matches_improved(
                winning_team_id, league_id, season, not losing_is_home
            )
            

            losing_goals_for, losing_goals_against = self.extract_goals_for_and_against(losing_stats_str)
            winning_goals_for, winning_goals_against = self.extract_goals_for_and_against(winning_stats_str)
            

            if losing_goals_against > 7:
                return "❌ no (الخاسر استقبل أكثر من 7 أهداف)"
            

            if (losing_goals_against - winning_goals_against) > 2:
                    return "❌ no (الخاسر استقبل عدد أهداف مرتفع)"

                                                # ============================================================

            if losing_goals_for >= winning_goals_for:
                return "✅ yes"
            
            return "❌ no (الأهداف المسجلة للخاسر أقل)"
            
        except Exception as e:
            print(f"Error in filter_condition_2: {e}")
            return "❌ no"

    def combined_filter_condition(self, match_data):
        condition1_result = self.filter_condition_1(match_data)
        condition2_result = self.filter_condition_2(match_data)
        
        if condition1_result == "✅ yes" and condition2_result == "✅ yes":
            return "✅ yes"
        
        return "❌ no"
        
    def filter_condition_combined_1_and_2(self, match_data):
        condition1_result = self.filter_condition_1(match_data)
        if condition1_result != "✅ yes":
            return "❌ no"

        condition2_result = self.filter_condition_2(match_data)
        
        if condition2_result == "✅ yes":
            return "✅ yes"
        
        return "❌ no"

    def apply_filter_condition_1(self):
        self.set_filter_logic(self.filter_condition_1, "One Team Scored/No Goals")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Condition 1: One team scored or no goals")

    def apply_filter_condition_2(self):
        self.set_filter_logic(self.filter_condition_2, "Loser Scored More (Last 3)")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Condition 2: Losing team scored more in last 3 matches")

    def apply_combined_filter(self):
        self.set_filter_logic(self.combined_filter_condition, "Combined Filter (1 and 2)")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Combined Filter (Conditions 1 and 2)")

    def apply_combined_filter_1_and_2(self):
        self.set_filter_logic(self.filter_condition_combined_1_and_2, "Condition 1 + 2")
        self.run_filter_process_threaded()
        self.show_snackbar("Applied Combined Filter: One Team Scored/No Goals AND Loser Stats")
    
    def apply_combined_filter_on_start(self):
        self.set_filter_logic(self.filter_condition_combined_1_and_2, "Condition 1 + 2 (Auto)")
        Clock.schedule_once(lambda dt: self.run_filter_process_threaded(), 0)
        self.show_snackbar("Auto-Filter Applied: Condition 1 + 2")

    def reset_filter_ui(self):
        self.reset_filter()
        if self.current_tab == 'live':
            self.show_live_matches()
        self.show_snackbar("Filter reset")

    def set_filter_logic(self, new_logic_function, filter_name="Custom"):
        self.filter_condition = new_logic_function
        self.current_filter = filter_name

    def run_filter_process_threaded(self):
        if self._is_filtering:
            return
            
        self._is_filtering = True
        
        def apply_filter():
            try:
                filtered_matches = []
                filter_results = {}
                
                live_matches = self.fetch_live_matches_sync()
                
                relevant_matches = [
                    match for match in live_matches 
                    if match.get('status') in ['1H', '2H', 'HT', 'ET', 'P', 'BT', 'LIVE']
                ]
                
                required_league_ids = self.get_required_league_ids()
                if required_league_ids:
                    relevant_matches = [
                        match for match in relevant_matches
                        if match.get('league_id') in required_league_ids
                    ]

                hidden_ids = {m.get('id') for m in self.hidden_matches}
                relevant_matches = [
                    match for match in relevant_matches 
                    if match.get('id') not in hidden_ids
                ]
                
                for match in relevant_matches:
                    match_id = match.get('id')
                    result = self.apply_filter_condition(match)
                    filter_results[match_id] = result
                    
                    if result == "✅ yes":
                        filtered_matches.append(match)
                
                Clock.schedule_once(lambda dt: self._update_ui_with_filtered_matches(
                    filtered_matches, filter_results
                ), 0)
                
            except Exception as e:
                print(f"Filter error: {e}")
                Clock.schedule_once(lambda dt: self._handle_filter_error(e), 0)
        
        threading.Thread(target=apply_filter, daemon=True).start()

    def apply_filter_condition(self, match_data):
        return self.filter_condition(match_data)

    @mainthread
    def _update_ui_with_filtered_matches(self, filtered_matches, filter_results):
        self.filtered_matches = filtered_matches
        self.filter_results = filter_results
        self._is_filtering = False
        
        if self.current_tab == 'live' and not self.calendar_mode:
            self.display_filtered_matches()

    def display_filtered_matches(self):
        container = self.root.ids.main_list
        container.clear_widgets()
        
        if self._is_filtering:
            self.show_loading("Applying filter...")
            return

        hidden_ids = {m.get('id') for m in self.hidden_matches}
        final_filtered_matches = [
            match for match in self.filtered_matches 
            if match.get('id') not in hidden_ids
        ]
            
        if final_filtered_matches:
            filter_info = MDLabel(
                text=f"🔍 Active Filter: {self.current_filter} | Live Matches: {len(final_filtered_matches)}",
                font_style='Button',
                halign='center',
                theme_text_color='Primary',
                bold=True,
                size_hint_y=None,
                height=dp(30)
            )
            container.add_widget(filter_info)
            
            organized_live_matches = self.organize_live_matches_by_minute(final_filtered_matches)
            
            if organized_live_matches:
                live_header = OneLineListItem(text=f"🔴 LIVE MATCHES ({len(organized_live_matches)})")
                live_header.md_bg_color = get_color_from_hex("#FFEBEE")
                container.add_widget(live_header)
                
                for match in organized_live_matches:
                    item = OptimizedCompactMatchItem(match_data=match)
                    container.add_widget(item)
            
            if not organized_live_matches:
                 self.show_empty_message("No live matches match filter conditions")

        else:
            self.show_empty_message("No live matches match filter conditions")

    def check_single_match_condition(self, match_data):
        match_id = match_data.get('id')
        
        if match_id in self.filter_results:
            return self.filter_results[match_id]
        
        result = self.apply_filter_condition(match_data)
        self.filter_results[match_id] = result
        
        return result

    def reset_filter(self):
        self.filtered_matches = []
        self.filter_results = {}
        self._is_filtering = False
        self.filter_condition = self.default_filter_condition
        self.current_filter = "No Filter"

    def clear_filter_cache(self):
        self.filter_results.clear()

    def start_filtering(self):
        self._is_filtering = True
        self.show_loading("Applying filter...")

    def stop_filtering(self):
        self._is_filtering = False

    def schedule_auto_filter(self, interval=None):
        if interval:
            self.filter_interval = interval
        
        if self._auto_filter_event:
            self._auto_filter_event.cancel()
        
        self._auto_filter_event = Clock.schedule_interval(
            lambda dt: self.run_filter_process_threaded(), 
            self.filter_interval
        )

    def _handle_filter_error(self, error):
        self._is_filtering = False
        self.show_snackbar(f"Filter error: {error}")

    def load_leagues_and_matches(self):
        self.show_loading("🚀 Starting Football App", 0, "Initializing...")
        
        self.loading_thread = threading.Thread(target=self._load_with_progress, daemon=True)
        self.loading_thread.start()

    def _load_with_progress(self):
        total_steps = 5
        current_step = 0
        
        try:
            current_step += 1
            progress = (current_step / total_steps) * 100
            self.update_loading_status(progress, "🔌 Connecting to server...")
            time.sleep(0.5)
            
            current_step += 1
            progress = (current_step / total_steps) * 100
            self.update_loading_status(progress, "🏆 Loading leagues...")
            leagues = self.fetch_leagues()
            
            if leagues:
                current_step += 1
                progress = (current_step / total_steps) * 100
                self.update_loading_status(progress, "📊 Processing data...")
                self.all_leagues = leagues
                self.leagues_loaded = True
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                self.update_loading_status(progress, "⚽ Loading live matches...")
                live_matches = self.fetch_live_matches_sync()
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                self.update_loading_status(progress, "🎯 Applying filters...")
                
                if live_matches:
                    self.update_ui_with_matches(live_matches)
                    self.apply_combined_filter_on_start()
                else:
                    self.show_no_matches_in_main_thread()
            else:
                self.show_error_in_main_thread("Could not load leagues")
                
            self.update_loading_status(100, "✅ Ready!")
            time.sleep(0.3)
            
        except Exception as e:
            self.show_error_in_main_thread(str(e))
        finally:
            self._is_loading = False

    @mainthread
    def update_loading_status(self, progress, status):
        container = self.root.ids.main_list
        for widget in container.children:
            if isinstance(widget, LoadingWidget):
                widget.progress_value = progress
                widget.status_text = status
                break

    def actualaser_refresh(self):
        self._animate_refresh_button()
        
        self.show_snackbar("🔄 Actualaser - Quick Refresh")
        
        if self.current_filter != "No Filter":
            self.run_filter_process_threaded()
        else:
            threading.Thread(target=self._quick_refresh, daemon=True).start()

    def _animate_refresh_button(self):
        try:
            self.show_snackbar("⚡ Refreshing...")
        except:
            pass

    def _quick_refresh(self):
        try:
            self.show_loading("Quick Refresh...", 0, "Updating data...")
            
            new_matches = self.fetch_live_matches_for_update()
            if new_matches:
                self.update_matches_data(new_matches)
                self.show_snackbar("✅ Data updated successfully")
            else:
                self.show_snackbar("⚠️ No new data available")
                
        except Exception as e:
            self.show_snackbar(f"❌ Refresh error: {str(e)}")


if __name__ == '__main__':
    ProfessionalFootballApp().run()

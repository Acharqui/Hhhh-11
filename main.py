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


class DatabaseManager:
    """مدير قاعدة البيانات باستخدام SQLite"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """تهيئة قاعدة البيانات وإنشاء الجداول"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # جدول المباريات المخفية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hidden_matches (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                hidden_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الدوريات المفضلة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorite_leagues (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الدوريات المختارة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS selected_leagues (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول المباريات المفضلة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorite_matches (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        return sqlite3.connect(self.db_path)
    
    # ===== وظائف المباريات المخفية =====
    def add_hidden_match(self, match_data):
        """إضافة مباراة مخفية"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            match_id = str(match_data.get('id'))
            data_json = json.dumps(match_data)
            
            cursor.execute(
                'INSERT OR REPLACE INTO hidden_matches (id, data) VALUES (?, ?)',
                (match_id, data_json)
            )
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding hidden match: {e}")
            return False
        finally:
            conn.close()
    
    def remove_hidden_match(self, match_id):
        """إزالة مباراة مخفية"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM hidden_matches WHERE id = ?', (str(match_id),))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing hidden match: {e}")
            return False
        finally:
            conn.close()
    
    def get_hidden_matches(self):
        """جلب جميع المباريات المخفية"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT data FROM hidden_matches ORDER BY hidden_at DESC')
            rows = cursor.fetchall()
            
            matches = []
            for row in rows:
                try:
                    match_data = json.loads(row[0])
                    matches.append(match_data)
                except json.JSONDecodeError:
                    continue
            
            return matches
        except Exception as e:
            print(f"Error getting hidden matches: {e}")
            return []
        finally:
            conn.close()
    
    def is_match_hidden(self, match_id):
        """التحقق إذا كانت المباراة مخفية"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT 1 FROM hidden_matches WHERE id = ?', (str(match_id),))
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def clear_hidden_matches(self):
        """مسح جميع المباريات المخفية"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM hidden_matches')
            conn.commit()
            return True
        except Exception as e:
            print(f"Error clearing hidden matches: {e}")
            return False
        finally:
            conn.close()
    
    def get_hidden_match_ids(self):
        """جلب فقط IDs للمباريات المخفية (أكثر كفاءة)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id FROM hidden_matches')
            rows = cursor.fetchall()
            return {str(row[0]) for row in rows}
        except Exception as e:
            print(f"Error getting hidden match IDs: {e}")
            return set()
        finally:
            conn.close()
    
    # ===== وظائف الدوريات المفضلة =====
    def add_favorite_league(self, league_id, league_name, league_data=None):
        """إضافة دوري مفضل"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            data_json = json.dumps(league_data) if league_data else json.dumps({'name': league_name})
            
            cursor.execute(
                'INSERT OR REPLACE INTO favorite_leagues (id, name, data) VALUES (?, ?, ?)',
                (str(league_id), league_name, data_json)
            )
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding favorite league: {e}")
            return False
        finally:
            conn.close()
    
    def remove_favorite_league(self, league_id):
        """إزالة دوري مفضل"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM favorite_leagues WHERE id = ?', (str(league_id),))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing favorite league: {e}")
            return False
        finally:
            conn.close()
    
    def get_favorite_leagues(self):
        """جلب جميع الدوريات المفضلة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id, name, data FROM favorite_leagues ORDER BY added_at DESC')
            rows = cursor.fetchall()
            
            leagues = []
            for row in rows:
                league_id, league_name, data_json = row
                try:
                    league_data = json.loads(data_json) if data_json else {}
                    leagues.append({
                        'id': league_id,
                        'name': league_name,
                        **league_data
                    })
                except json.JSONDecodeError:
                    leagues.append({
                        'id': league_id,
                        'name': league_name
                    })
            
            return leagues
        except Exception as e:
            print(f"Error getting favorite leagues: {e}")
            return []
        finally:
            conn.close()
    
    def is_league_favorite(self, league_id):
        """التحقق إذا كان الدوري مفضلاً"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT 1 FROM favorite_leagues WHERE id = ?', (str(league_id),))
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    # ===== وظائف الدوريات المختارة =====
    def add_selected_league(self, league_id, league_name, league_data=None):
        """إضافة دوري مختار"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            data_json = json.dumps(league_data) if league_data else json.dumps({'name': league_name})
            
            cursor.execute(
                'INSERT OR REPLACE INTO selected_leagues (id, name, data) VALUES (?, ?, ?)',
                (str(league_id), league_name, data_json)
            )
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding selected league: {e}")
            return False
        finally:
            conn.close()
    
    def remove_selected_league(self, league_id):
        """إزالة دوري مختار"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM selected_leagues WHERE id = ?', (str(league_id),))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing selected league: {e}")
            return False
        finally:
            conn.close()
    
    def get_selected_leagues(self):
        """جلب جميع الدوريات المختارة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id, name, data FROM selected_leagues ORDER BY added_at DESC')
            rows = cursor.fetchall()
            
            leagues = []
            for row in rows:
                league_id, league_name, data_json = row
                try:
                    league_data = json.loads(data_json) if data_json else {}
                    leagues.append({
                        'id': league_id,
                        'name': league_name,
                        **league_data
                    })
                except json.JSONDecodeError:
                    leagues.append({
                        'id': league_id,
                        'name': league_name
                    })
            
            return leagues
        except Exception as e:
            print(f"Error getting selected leagues: {e}")
            return []
        finally:
            conn.close()
    
    def is_league_selected(self, league_id):
        """التحقق إذا كان الدوري مختاراً"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT 1 FROM selected_leagues WHERE id = ?', (str(league_id),))
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def get_selected_league_ids(self):
        """جلب IDs فقط للدوريات المختارة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id FROM selected_leagues')
            rows = cursor.fetchall()
            return {str(row[0]) for row in rows}
        except Exception as e:
            print(f"Error getting selected league IDs: {e}")
            return set()
        finally:
            conn.close()
    
    # ===== وظائف المباريات المفضلة =====
    def add_favorite_match(self, match_data):
        """إضافة مباراة مفضلة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            match_id = str(match_data.get('id'))
            data_json = json.dumps(match_data)
            
            cursor.execute(
                'INSERT OR REPLACE INTO favorite_matches (id, data) VALUES (?, ?)',
                (match_id, data_json)
            )
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding favorite match: {e}")
            return False
        finally:
            conn.close()
    
    def remove_favorite_match(self, match_id):
        """إزالة مباراة مفضلة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM favorite_matches WHERE id = ?', (str(match_id),))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing favorite match: {e}")
            return False
        finally:
            conn.close()
    
    def get_favorite_matches(self):
        """جلب جميع المباريات المفضلة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT data FROM favorite_matches ORDER BY added_at DESC')
            rows = cursor.fetchall()
            
            matches = []
            for row in rows:
                try:
                    match_data = json.loads(row[0])
                    matches.append(match_data)
                except json.JSONDecodeError:
                    continue
            
            return matches
        except Exception as e:
            print(f"Error getting favorite matches: {e}")
            return []
        finally:
            conn.close()
    
    def is_match_favorite(self, match_id):
        """التحقق إذا كانت المباراة مفضلة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT 1 FROM favorite_matches WHERE id = ?', (str(match_id),))
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def get_favorite_match_ids(self):
        """جلب IDs فقط للمباريات المفضلة"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id FROM favorite_matches')
            rows = cursor.fetchall()
            return {str(row[0]) for row in rows}
        except Exception as e:
            print(f"Error getting favorite match IDs: {e}")
            return set()
        finally:
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
        
        # التحقق المباشر من قاعدة البيانات
        if not app.db.is_match_hidden(match_id):
            app.add_hidden_match(self.match_data)
            app.show_snackbar(f"Match hidden: {self.home_team} vs {self.away_team}")
        else:
            app.show_snackbar(f"Match already hidden: {self.home_team} vs {self.away_team}")
        
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
                        text_color: get_color_from_hex("#00FF00") if root.second_team_color == 'green' else (get_color_from_hex("#2196F3") if root.second_team_color == 'blue' else (get_color_from_hex("#FF0000") if root.second_team_color == 'red' else get_color_from_hex("#FFFFFF")))
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
    
    # ===========================================
    # CALENDAR FILTER PROPERTIES - ADDED
    # ===========================================
    calendar_filter_active = BooleanProperty(False)
    calendar_filter_type = StringProperty('perfect_1_1')
    
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
        
        # Filter system
        self.filtered_matches = []
        self.filter_results = {}
        self._is_filtering = False
        self.filter_condition = self.default_filter_condition
        self._auto_filter_event = None
        self.filter_interval = 600
        self.current_filter = "No Filter"
        
        # إعدادات التقويم
        self.current_calendar_date = datetime.now().date()
        self.calendar_mode = False
        
        # ===========================================
        # CALENDAR FILTER SYSTEM INIT - ADDED
        # ===========================================
        self.calendar_filtered_matches = []
        self.calendar_filter_results = {}
        self._is_calendar_filtering = False
        
        # Cache system for team stats
        self.team_stats_cache = OrderedDict()
        self.cache_max_size = 100
        
        # تهيئة مدير قاعدة البيانات
        db_path = os.path.join(self.user_data_dir, 'football_data.db')
        self.db = DatabaseManager(db_path)
        
        # الكاش للبيانات المخفية والمفضلة (لتجنب استعلامات SQL المتكررة)
        self._hidden_match_ids_cache = None
        self._hidden_match_ids_cache_time = None
        self._favorite_match_ids_cache = None
        self._favorite_match_ids_cache_time = None
        self._cache_timeout = 30  # ثانية

    def build(self):
        self.theme_cls.primary_palette = 'Blue'
        self.theme_cls.theme_style = 'Light'
        
        # تحميل البيانات من قاعدة البيانات
        self.load_favorites()
        self.load_hidden_matches()
        self.load_league_selection()
        self.load_favorite_leagues()

        self.update_time()
        Clock.schedule_interval(self.update_time, 60)
        
        # ===========================================
        # CALENDAR FILTER INITIALIZATION - ADDED
        # ===========================================
        self.calendar_filter_dir = os.path.join(self.user_data_dir, 'calendar_filter')
        if not os.path.exists(self.calendar_filter_dir):
            os.makedirs(self.calendar_filter_dir)
        
        self.load_calendar_filter_state()
        
        Clock.schedule_once(lambda dt: self.load_leagues_and_matches(), 0.5)
        Clock.schedule_once(lambda dt: self.schedule_auto_filter(), 10)
        
        return Builder.load_string(KV)
    
    def on_stop(self):
        if self._update_event:
            self._update_event.cancel()
            
        if self._auto_filter_event:
            self._auto_filter_event.cancel()
        
        super().on_stop()

    # ===== الوظائف المحسنة للبيانات المخفية =====
    
    def load_hidden_matches(self):
        """تحميل المباريات المخفية من قاعدة البيانات"""
        self.hidden_matches = self.db.get_hidden_matches()
        self._hidden_match_ids_cache = None  # إعادة تعيين الكاش
        self._hidden_match_ids_cache_time = None
    
    def get_hidden_match_ids(self):
        """الحصول على IDs المباريات المخفية مع كاش"""
        now = time.time()
        
        # التحقق إذا كان الكاش صالحاً
        if (self._hidden_match_ids_cache is not None and 
            self._hidden_match_ids_cache_time is not None and
            (now - self._hidden_match_ids_cache_time) < self._cache_timeout):
            return self._hidden_match_ids_cache
        
        # جلب جديد من قاعدة البيانات
        hidden_ids = self.db.get_hidden_match_ids()
        self._hidden_match_ids_cache = hidden_ids
        self._hidden_match_ids_cache_time = now
        
        return hidden_ids
    
    def get_favorite_match_ids(self):
        """الحصول على IDs المباريات المفضلة مع كاش"""
        now = time.time()
        
        # التحقق إذا كان الكاش صالحاً
        if (self._favorite_match_ids_cache is not None and 
            self._favorite_match_ids_cache_time is not None and
            (now - self._favorite_match_ids_cache_time) < self._cache_timeout):
            return self._favorite_match_ids_cache
        
        # جلب جديد من قاعدة البيانات
        favorite_ids = self.db.get_favorite_match_ids()
        self._favorite_match_ids_cache = favorite_ids
        self._favorite_match_ids_cache_time = now
        
        return favorite_ids
    
    def refresh_hidden_cache(self):
        """تحديث كاش المباريات المخفية"""
        self._hidden_match_ids_cache = None
        self._hidden_match_ids_cache_time = None
    
    def refresh_favorite_cache(self):
        """تحديث كاش المباريات المفضلة"""
        self._favorite_match_ids_cache = None
        self._favorite_match_ids_cache_time = None
    
    def add_hidden_match(self, match):
        """إضافة مباراة مخفية مع تحديث الكاش"""
        match_id = str(match.get('id'))
        
        # التحقق المباشر من قاعدة البيانات
        if not self.db.is_match_hidden(match_id):
            if self.db.add_hidden_match(match):
                # تحديث القائمة المحلية
                self.hidden_matches.append(match.copy())
                # تحديث الكاش
                self.refresh_hidden_cache()
                self.show_snackbar(f"Match hidden: {match.get('home_team')} vs {match.get('away_team')}")
                return True
            else:
                self.show_snackbar("Failed to hide match")
                return False
        else:
            self.show_snackbar(f"Match already hidden: {match.get('home_team')} vs {match.get('away_team')}")
            return True
    
    def remove_hidden_match(self, match_id):
        """إزالة مباراة مخفية مع تحديث الكاش"""
        if self.db.remove_hidden_match(match_id):
            # تحديث القائمة المحلية
            self.hidden_matches = [m for m in self.hidden_matches if str(m.get('id')) != str(match_id)]
            # تحديث الكاش
            self.refresh_hidden_cache()
            self.show_snackbar("Match unhidden")
            return True
        else:
            self.show_snackbar("Failed to unhide match")
            return False
    
    def clear_all_hidden_matches(self):
        """مسح جميع المباريات المخفية مع تحديث الكاش"""
        if self.db.clear_hidden_matches():
            self.hidden_matches = []
            self.refresh_hidden_cache()
            self.show_snackbar("All hidden matches cleared")
            return True
        else:
            self.show_snackbar("Failed to clear hidden matches")
            return False
    
    def is_hidden(self, match_id):
        """التحقق إذا كانت المباراة مخفية (باستخدام الكاش)"""
        hidden_ids = self.get_hidden_match_ids()
        return str(match_id) in hidden_ids
    
    # ===== الوظائف المحسنة للمباريات المفضلة =====
    
    def load_favorites(self):
        """تحميل المباريات المفضلة من قاعدة البيانات"""
        self.favorites = self.db.get_favorite_matches()
        self._favorite_match_ids_cache = None
        self._favorite_match_ids_cache_time = None
    
    def is_favorite(self, match_id):
        """التحقق إذا كانت المباراة مفضلة (باستخدام الكاش)"""
        favorite_ids = self.get_favorite_match_ids()
        return str(match_id) in favorite_ids
    
    def add_favorite(self, match):
        """إضافة مباراة مفضلة مع تحديث الكاش"""
        match_id = str(match.get('id'))
        
        if not self.is_favorite(match_id):
            if self.db.add_favorite_match(match):
                self.favorites.append(match.copy())
                self.refresh_favorite_cache()
                self.show_snackbar("Match added to favorites")
                if self.current_tab == 'live' and not self.calendar_mode:
                    self.show_live_matches()
                return True
            else:
                self.show_snackbar("Failed to add to favorites")
                return False
        else:
            self.show_snackbar("Match already in favorites")
            return True
    
    def remove_favorite(self, match_id):
        """إزالة مباراة مفضلة مع تحديث الكاش"""
        if self.db.remove_favorite_match(match_id):
            self.favorites = [f for f in self.favorites if str(f.get('id')) != str(match_id)]
            self.refresh_favorite_cache()
            self.show_snackbar("Match removed from favorites")
            if self.current_tab == 'live' and not self.calendar_mode:
                self.show_live_matches()
            elif self.current_tab == 'favorites':
                self.show_favorites()
            return True
        else:
            self.show_snackbar("Failed to remove from favorites")
            return False
    
    # ===== الوظائف المحسنة للدوريات =====
    
    def load_league_selection(self):
        """تحميل الدوريات المختارة من قاعدة البيانات"""
        self.selected_leagues = self.db.get_selected_leagues()
    
    def load_favorite_leagues(self):
        """تحميل الدوريات المفضلة من قاعدة البيانات"""
        self.favorite_leagues = self.db.get_favorite_leagues()
    
    def is_favorite_league(self, league_id):
        """التحقق إذا كان الدوري مفضلاً"""
        return self.db.is_league_favorite(league_id)
    
    def add_favorite_league(self, league_name, league_id):
        """إضافة دوري مفضل"""
        if not self.is_favorite_league(league_id):
            if self.db.add_favorite_league(league_id, league_name):
                self.favorite_leagues.append({'name': league_name, 'id': league_id})
                self.show_snackbar(f"League added to favorites: {league_name}")
                return True
            else:
                self.show_snackbar("Failed to add league to favorites")
                return False
        else:
            self.show_snackbar("League already in favorites")
            return True
    
    def remove_favorite_league(self, league_id):
        """إزالة دوري مفضل"""
        if self.db.remove_favorite_league(league_id):
            self.favorite_leagues = [f for f in self.favorite_leagues if f.get('id') != league_id]
            self.show_snackbar("League removed from favorites")
            if self.current_tab == 'favorites':
                self.show_favorites()
            return True
        else:
            self.show_snackbar("Failed to remove league from favorites")
            return False
    
    def is_league_selected(self, league_id):
        """التحقق إذا كان الدوري مختاراً"""
        return self.db.is_league_selected(league_id)
    
    # ===== الوظائف المحسنة لعرض المباريات =====
    
    def get_matches_without_favorites_and_hidden(self, matches_list):
        """تصفية المباريات المخفية والمفضلة (باستخدام الكاش)"""
        if not matches_list:
            return []
        
        # الحصول على IDs من الكاش
        hidden_ids = self.get_hidden_match_ids()
        favorite_ids = self.get_favorite_match_ids()
        
        filtered_list = []
        for match in matches_list:
            match_id = str(match.get('id'))
            status = match.get('status')
            
            # استبعاد المباريات المخفية
            if match_id in hidden_ids:
                continue

            # استبعاد المباريات المنتهية
            if status in ['FT', 'AET', 'PEN']:
                continue

            # استبعاد المباريات المفضلة
            if match_id in favorite_ids:
                continue

            filtered_list.append(match)
            
        return filtered_list
    
    # ===== تحديث البيانات مع التصفية =====
    
    @mainthread
    def update_matches_data(self, new_matches):
        """تحديث بيانات المباريات مع التصفية الفورية للمخفي"""
        if not new_matches:
            return
        
        new_matches_dict = {str(m.get('id')): m for m in new_matches}
        
        # الحصول على IDs المخفية من الكاش
        hidden_ids = self.get_hidden_match_ids()
        
        updated_self_matches = []
        should_refresh_ui = False
        
        for old_match in self.matches:
            match_id = str(old_match.get('id'))
            new_match = new_matches_dict.pop(match_id, None)
            
            # إذا كانت المباراة مخفية، نتخطاها
            if match_id in hidden_ids:
                continue
            
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

        # إضافة المباريات الجديدة فقط إذا لم تكن مخفية
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
    
    # ===== بقية الوظائف (بدون تغييرات رئيسية) =====
    
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
        if self.calendar_filter_active:
            filter_type_display = self.calendar_filter_type.replace('_', ' ').title()
            loading_msg = f"Loading scheduled matches for {target_date.strftime('%d/%m/%Y')}..."
            loading_msg += f"\nApplying {filter_type_display} filter..."
            self.show_loading(loading_msg)
        else:
            self.show_loading(f"Loading scheduled matches for {target_date.strftime('%d/%m/%Y')}...")
        
        def fetch_and_display():
            try:
                matches = self.fetch_matches_by_date_improved(target_date)
                processed_matches = self.process_matches_improved(matches)
                
                # تطبيق فلتر التقويم إذا كان نشطاً
                if self.calendar_filter_active:
                    final_matches = self.run_calendar_filter_process(processed_matches)
                    print(f"✅ After filter: {len(final_matches)} matches remain")
                else:
                    final_matches = processed_matches
                    print(f"ℹ️ No filter applied, showing all {len(final_matches)} matches")
                
                Clock.schedule_once(lambda dt: self.display_calendar_matches_improved(final_matches, target_date), 0)
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
                    print(f"✅ تم العثور على {len(matches)} مباراة")
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

        # إضافة حالة الفلتر في العنوان إذا كان نشطاً
        if self.calendar_filter_active:
            filter_type_display = self.calendar_filter_type.replace('_', ' ').title()
            date_label += f" - [{filter_type_display} FILTER ACTIVE]"
        
        header = OneLineListItem(text=date_label)
        header.md_bg_color = get_color_from_hex("#E3F2FD")
        container.add_widget(header)
        
        if matches:
            # فقط إذا كان الفلتر غير نشط، نطبق تصفية الدوريات
            if not self.calendar_filter_active:
                required_league_ids = self.get_required_league_ids()
                
                if required_league_ids:
                    filtered_matches = [
                        match for match in matches
                        if match.get('league_id') in required_league_ids
                    ]
                    print(f"🔍 بعد التصفية حسب الدوري: {len(filtered_matches)} مباراة مجدولة")
                else:
                    filtered_matches = matches
            else:
                # إذا كان الفلتر نشطاً، نستخدم المباريات التي تمت تصفيتها بالفعل
                filtered_matches = matches
                
            # تطبيق التصفية للمباريات المخفية والمفضلة
            final_matches = self.get_matches_without_favorites_and_hidden(filtered_matches)
            
            if self.calendar_filter_active:
                print(f"🎯 بعد تطبيق فلتر التقويم: {len(final_matches)} مباراة مجدولة")
            else:
                print(f"ℹ️ بدون فلتر: {len(final_matches)} مباراة مجدولة")
            
            if final_matches:
                count_text = f"Found {len(final_matches)} scheduled matches"
                if self.calendar_filter_active:
                    count_text += f" (with {self.calendar_filter_type.replace('_', ' ')} filter)"
                    
                count_label = MDLabel(
                    text=count_text,
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
                if self.calendar_filter_active:
                    self.show_empty_message(f"No matches found with {self.calendar_filter_type.replace('_', ' ')} filter")
                else:
                    self.show_empty_message(f"No scheduled matches found for {target_date.strftime('%d/%m/%Y')}")
        else:
            if self.calendar_filter_active:
                self.show_empty_message(f"No scheduled matches with {self.calendar_filter_type.replace('_', ' ')} filter")
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
                'last': 10
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

    # ===========================================
    # CALENDAR FILTER FUNCTIONS - ADDED
    # ===========================================

    def fetch_team_last_matches(self, team_id, league_id, season, is_home=True):
        """جلب آخر 3 مباريات للفريق في نفس الدوري (Home أو Away فقط)"""
        
        # --- [استخدام الكاش] ---
        cache_key = f"last_matches_{team_id}_{league_id}_{season}_{'home' if is_home else 'away'}"
        cached_data = self.team_stats_cache.get(cache_key)
        if cached_data is not None:
            return cached_data
        # ---------------------------------------------------------

        try:
            url = f"{self.base_url}/fixtures"
            params = {
                'team': team_id,
                'league': league_id,
                'season': season,
                'last': 15  # نجلب 15 مباراة لضمان وجود 3 مباريات من النوع المطلوب
            }
            
            print(f"🔍 Fetching last matches for team {team_id}, home={is_home}")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('response'):
                    all_matches = self.process_api_response_improved(data['response'])
                    
                    # تصفية المباريات حسب النوع المطلوب
                    filtered_matches = []
                    for match in all_matches:
                        # التحقق من حالة المباراة (نأخذ فقط المباريات المنتهية FT)
                        if match.get('status') != 'FT':
                            continue
                        
                        if is_home:
                            # نريد مباريات Home فقط (الفريق هو المضيف)
                            if match.get('home_team_id') == team_id:
                                filtered_matches.append(match)
                        else:
                            # نريد مباريات Away فقط (الفريق هو الضيف)
                            if match.get('away_team_id') == team_id:
                                filtered_matches.append(match)
                    
                    # ترتيب المباريات من الأحدث إلى الأقدم
                    filtered_matches.sort(key=lambda x: x.get('time', ''), reverse=True)
                    
                    # أخذ آخر 3 مباريات فقط
                    final_matches = filtered_matches[:3]
                    
                    print(f"✅ Found {len(final_matches)} last matches for team {team_id}")
                    
                    # --- [حفظ في الكاش] ---
                    self.team_stats_cache[cache_key] = final_matches
                    return final_matches
            
            print(f"⚠️ No matches found for team {team_id}")
            return []
            
        except Exception as e:
            print(f"❌ Error fetching last matches for team {team_id}: {e}")
            return []

    def calculate_total_goals(self, matches, is_home=True):
        """حساب إجمالي الأهداف في المباريات"""
        if not matches or len(matches) < 3:
            # إذا لم يكن هناك 3 مباريات، نعتبر الأهداف = 0
            return 0
        
        total_goals = 0
        
        for idx, match in enumerate(matches[:3]):  # نأخذ فقط آخر 3 مباريات
            try:
                # التحقق من أن المباراة منتهية (FT)
                if match.get('status') != 'FT':
                    continue
                    
                if is_home:
                    goals = match.get('home_score')
                else:
                    goals = match.get('away_score')
                
                if goals is not None:
                    total_goals += int(goals)
                    print(f"   Match {idx+1}: {goals} goals")
            except (ValueError, TypeError):
                continue
        
        return total_goals

    def filter_condition_perfect_1_1(self, match_data):

        forbidden_groups = [
            {
                'current_rank_1': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                'last_rank_2': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (10, 11), (10, 12), (10, 13), (10, 14)},
            },
            {
                'current_rank_1': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
                'last_rank_2': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (6, 17), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
            },
            {
                'current_rank_1': {(7, 8), (7, 9), (8, 9), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 14)},
                'last_rank_2': {(1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 13), (2, 10), (3, 10), (3, 11), (3, 12), (4, 10), (4, 11), (4, 12), (5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (6, 17), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (12, 13), (12, 14), (12, 15), (13, 14), (13, 15), (14, 15), (14, 16)},
            },
            {
                'current_rank_1': {(9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (13, 14), (13, 15), (13, 16), (13, 17), (13, 18), (14, 15), (14, 16), (14, 17), (14, 18)},
                'last_rank_2': {(1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (1, 13), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (5, 17), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16), (6, 17), (7, 10), (7, 11), (7, 12), (7, 13), (7, 14), (7, 15), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 10), (9, 11), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (10, 11), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (12, 13), (12, 14), (12, 15), (12, 16), (12, 17), (13, 14), (13, 15), (13, 16), (14, 15), (14, 16), (14, 17), (14, 18)},
            },
            {
                'current_rank_1': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (7, 8), (7, 9), (8, 9), (5, 10), (5, 11), (5, 12), (6, 10), (6, 11), (6, 12), (7, 10), (7, 11), (7, 12), (8, 10), (8, 11), (8, 12)},
                'last_rank_2': {(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (4, 3), (5, 1), (5, 2), (5, 3), (5, 4), (6, 1), (6, 2), (6, 3), (6, 4), (7, 1), (7, 2), (7, 3), (7, 4), (8, 1), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (11, 4), (10, 4)},
            },
            {
                'current_rank_1': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
                'last_rank_2': {(6, 5), (7, 5), (7, 6), (8, 5), (8, 6), (9, 5), (9, 6), (10, 5), (10, 6), (11, 5), (11, 6), (12, 5), (12, 6)},
            },
            {
                'current_rank_1': {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9), (3, 7), (3, 8), (3, 9), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15), (4, 16)},
                'last_rank_2': {(9, 7), (10, 8), (10, 9), (11, 7), (11, 8), (11, 9), (12, 7), (12, 8), (12, 9), (13, 7), (13, 8), (13, 9), (14, 7), (14, 8), (14, 9), (15, 7), (15, 8), (15, 9), (16, 9), (10, 11), (11, 10), (12, 10), (12, 11), (13, 10), (13, 11), (13, 12), (14, 10), (14, 11), (14, 12), (14, 13), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14), (16, 10), (16, 11), (16, 12), (16, 13), (16, 14), (16, 15)},
            },
            {
                'current_rank_1': {(3, 2), (4, 2), (4, 3), (5, 2), (5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (11, 4), (10, 4)},
                'last_rank_2': {(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (3, 9), (4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (1, 10), (1, 11), (1, 12), (2, 10), (2, 11), (2, 12), (2, 13), (2, 14), (3, 10), (3, 11), (3, 12), (3, 13), (3, 14), (3, 15), (4, 10), (4, 11), (4, 12), (4, 13), (4, 14), (4, 15)},
            },
            {

                'current_rank_1': {(11, 7), (10, 7), (9, 7), (11, 8), (10, 8), (14, 9), (13, 9), (12, 9), (11, 9), (15, 10), (14, 10), (13, 10), (12, 10), (13, 11), (13, 12), (12, 11)},
                'last_rank_2': {(3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
            },
            {
                'current_rank_1': {(10, 6), (9, 6), (8, 6), (7, 6), (10, 5), (9, 5), (8, 5), (7, 5), (6, 5)},
                'last_rank_2': {(2, 3), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), (4, 5), (4, 6), (4, 7), (4, 8)},
            },
            {

                'current_rank_1': {(5, 3), (5, 4), (6, 2), (6, 3), (6, 4), (7, 2), (7, 3), (7, 4), (8, 2), (8, 3), (8, 4), (9, 2), (9, 3), (9, 4), (11, 4), (10, 4), (10, 5), (10, 6), (10, 7), (10, 8), (10, 9), (9, 5), (9, 5), (9, 6), (9, 7), (9, 8), (8, 5), (8, 6), (8, 7), (7, 5), (7, 6), (6, 5)},
                'last_rank_2': {(5, 6), (5, 7), (5, 8), (5, 9), (6, 7), (6, 8), (6, 9), (5, 10), (5, 11), (5, 12), (5, 13), (5, 14), (5, 15), (5, 16), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), (6, 15), (6, 16)},
            },
            {
                'current_rank_1': {(6, 4), (7, 6), (10, 6), (10, 7), (10, 9), (11, 6), (11, 7), (11, 9), (11, 10), (12, 6), (12, 7), (12, 9), (13, 7), (14, 9), (15, 9), (16, 9), (11, 10), (12, 10), (12, 11), (13, 10), (13, 11), (13, 12), (14, 10), (14, 11), (14, 12), (14, 13), (15, 10), (15, 11), (15, 12), (15, 13), (15, 14), (16, 10), (16, 11), (16, 12), (16, 13), (16, 14), (16, 15), (17, 15)},
                'last_rank_2': {(7, 12), (7, 13), (7, 14), (7, 15), (8, 12), (8, 13), (8, 14), (8, 15), (8, 16), (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (10, 12), (10, 13), (10, 14), (10, 15), (10, 16), (10, 17), (10, 18), (11, 12), (11, 13), (11, 14), (11, 15), (11, 16), (11, 17), (11, 18), (12, 14), (12, 15), (12, 16), (12, 17), (12, 18), (13, 15), (13, 16)},
            },
            {

                'current_rank_1': {(7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6)},
                'last_rank_2': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (10, 6), (9, 6), (8, 7), (8, 6), (7, 6), (11, 8), (10, 8), (9, 8), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13)},
            },
            {
                'current_rank_1': {(13, 7), (12, 7), (11, 7), (10, 7), (9, 7)},
                'last_rank_2': {(6, 2), (5, 2), (4, 2), (8, 3), (7, 3), (6, 3), (5, 3), (8, 4), (7, 4), (6, 4), (5, 4)},
            },
            {

                'current_rank_1': {(12, 8), (11, 8), (10, 8), (9, 8)},
                'last_rank_2': {(6, 2), (5, 2), (4, 2), (9, 3), (8, 3), (7, 3), (6, 3), (5, 3), (8, 4), (7, 4), (6, 4), (5, 4), (4, 1), (3, 1)},
            },
            {
                'current_rank_1': {(16, 8), (15, 8), (14, 8), (13, 8), (12, 8), (11, 8), (10, 8), (9, 8)},
                'last_rank_2': {(11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (12, 6), (11, 6), (11, 10), (10, 6), (9, 6), (8, 6), (7, 6), (12, 8), (11, 8), (10, 9), (10, 8), (9, 8), (15, 9), (14, 9), (13, 9), (12, 9), (11, 9), (10, 9), (15, 10), (15, 11), (15, 12), (15, 13), (16, 11), (14, 10), (12, 10)},
            },
            {
                'current_rank_1': {(14, 10), (13, 10), (12, 10), (11, 10), (9, 10), (14, 11), (13, 11), (12, 11), (14, 12), (13, 12)},
                'last_rank_2': {(14, 7), (15, 7), (13, 7), (12, 7), (14, 8), (15, 8), (13, 8), (12, 8), (15, 9), (11, 8), (11, 7), (14, 9), (13, 9), (12, 9), (11, 9), (12, 5), (11, 5), (10, 5), (9, 5), (8, 5), (7, 5), (6, 5), (10, 4), (9, 4), (8, 4), (7, 4), (6, 4), (5, 4)},
            }
        ]
        
        try:
            league_id = match_data['league_id']
            season = match_data['season']
            home_team_id = match_data['home_team_id']
            away_team_id = match_data['away_team_id']
            
            # 1. جلب بيانات آخر 3 مباريات والأهداف
            home_last_matches = self.fetch_team_last_matches(home_team_id, league_id, season, is_home=True)
            away_last_matches = self.fetch_team_last_matches(away_team_id, league_id, season, is_home=False)
            
            # التحقق من توفر 3 مباريات منتهية (FT)
            if len(home_last_matches) < 3 or len(away_last_matches) < 3:
                return f"✅ yes (no last 3 match)"
            
            home_total_goals = self.calculate_total_goals(home_last_matches, is_home=True)
            away_total_goals = self.calculate_total_goals(away_last_matches, is_home=False)
            
            # 2. القاعدة الذهبية (التعادل في الأهداف)
            if home_total_goals == away_total_goals:
                return f"✅ yes (Goals Equal: {home_total_goals}-{away_total_goals})"
            
            # 3. تحديد الفريق الهدف (Target)
            if home_total_goals > away_total_goals:
                target_is_home = True
                target_goals = home_total_goals
                other_goals = away_total_goals
                target_id = home_team_id
            else:
                target_is_home = False
                target_goals = away_total_goals
                other_goals = home_total_goals
                target_id = away_team_id
            
            target_name = match_data['home_team'] if target_is_home else match_data['away_team']

            # 4. جلب الترتيب الحالي والماضي
            home_standings = self.fetch_team_standings(home_team_id, league_id, season)
            away_standings = self.fetch_team_standings(away_team_id, league_id, season)

            ch_raw = home_standings.get('current_rank')
            ca_raw = away_standings.get('current_rank')

            if ch_raw == 'N/A' or ca_raw == 'N/A':
                return f"❌ no (Goals: {target_goals}-{other_goals} - No current rank for one team)"

            try:
                ch = int(ch_raw)
                ca = int(ca_raw)
            except:
                return f"✅ yes (Target: {target_name} with {target_goals} goals vs {other_goals} - Invalid current rank)"

            lh_raw = home_standings.get('last_rank')
            la_raw = away_standings.get('last_rank')
            
            lh_type = home_standings.get('last_rank_type')
            la_type = away_standings.get('last_rank_type')
            
            # استبعاد الفرق الصاعدة/الهابطة
            if lh_type in ['promoted', 'relegated', 'new_team'] or la_type in ['promoted', 'relegated', 'new_team']:
                return f"❌ no (Goals: {target_goals}-{other_goals} - Promoted/Relegated/New Team)"

            try:
                lh = int(str(lh_raw)) if str(lh_raw).isdigit() else 'N/A'
                la = int(str(la_raw)) if str(la_raw).isdigit() else 'N/A'
                
                if lh == 'N/A' or la == 'N/A':
                    return f"❌ no (Goals: {target_goals}-{other_goals} - Invalid last rank format)"
            except:
                 return f"❌ no (Goals: {target_goals}-{other_goals} - Invalid last rank format)"
            
            # 5. تطبيق قواعد الاستبعاد الصارمة (Forbidden Groups)
            if target_is_home:
                current_pair = (ch, ca)
                last_pair = (lh, la)
            else:
                current_pair = (ca, ch)
                last_pair = (la, lh)

            for group in forbidden_groups:
                if current_pair in group['current_rank_1']:
                    if last_pair in group['last_rank_2']:
                        target_name = match_data['home_team'] if target_is_home else match_data['away_team']
                        return f"❌ no (Forbidden: {target_name} with {target_goals} goals vs {other_goals}, Current: {current_pair}, Last: {last_pair})"
            
            # 6. قاعدة الترتيب (شرط التوافق)
            target_current_rank = ch if target_is_home else ca
            other_current_rank = ca if target_is_home else ch
            
            target_last_rank = lh if target_is_home else la
            other_last_rank = la if target_is_home else lh

            # الشرط السابع: الفريق الهدف يجب أن يكون ترتيبه الحالي أفضل من الفريق الآخر
            if target_current_rank >= other_current_rank:
                 return f"✅ yes (Goals: {target_goals}-{other_goals} - Target Rank {target_current_rank} is not better than Other Rank {other_current_rank})"
            
            # تم قبول المباراة بعد اجتياز جميع الشروط
            return f"✅ yes (Goals: {target_goals}-{other_goals} | Target Rank: {target_current_rank} | Other Rank: {other_current_rank})"

        except Exception as e:
            print(f"ERROR in filter_condition_perfect_1_1: {e} for match {match_data.get('id')}")
            return f"❌ no (Error in filter: {str(e)[:50]})"

    def fetch_team_standings(self, team_id, league_id, season):
        """جلب ترتيب الفريق مع استخدام الكاش"""
        cache_key = f"standings_{team_id}_{league_id}_{season}"
        
        if cache_key in self.team_stats_cache:
            return self.team_stats_cache[cache_key]
        
        standings = self.fetch_team_standings_improved(team_id, league_id, season)
        self.team_stats_cache[cache_key] = standings
        
        # إدارة حجم الكاش
        if len(self.team_stats_cache) > self.cache_max_size:
            oldest_key = next(iter(self.team_stats_cache))
            del self.team_stats_cache[oldest_key]
        
        return standings

    def run_calendar_filter_process(self, matches):
        if not self.calendar_filter_active:
            return matches
            
        if self._is_calendar_filtering:
            return matches
        
        self._is_calendar_filtering = True
        
        try:
            filtered_matches = []
            filter_results = {}
            
            # الحصول على الدوريات المختارة من قاعدة البيانات SQLite
            selected_leagues = self.db.get_selected_leagues()
            if not selected_leagues:
                print("⚠️ No leagues selected in database, returning all matches")
                self._is_calendar_filtering = False
                return matches
            
            selected_league_ids = {str(league['id']) for league in selected_leagues}
            print(f"📊 Selected leagues for filtering: {len(selected_league_ids)} leagues")
            
            if self.calendar_filter_type == 'perfect_1_1':
                filter_func = self.filter_condition_perfect_1_1
            else:
                filter_func = self.filter_condition_perfect_1_1
            
            print(f"🔍 Applying calendar filter '{self.calendar_filter_type}' to {len(matches)} matches")
            
            for match in matches:
                match_id = match.get('id')
                league_id = str(match.get('league_id', ''))
                
                if league_id not in selected_league_ids:
                    continue
                
                result = filter_func(match)
                filter_results[match_id] = result
                
                if "✅ yes" in result:
                    filtered_matches.append(match)
            
            print(f"✅ Filtered matches: {len(filtered_matches)} out of {len(matches)} (from selected leagues only)")
            
            self.calendar_filtered_matches = filtered_matches
            self.calendar_filter_results = filter_results
            self._is_calendar_filtering = False
            
            return filtered_matches
            
        except Exception as e:
            print(f"❌ Error in calendar filter process: {e}")
            self._is_calendar_filtering = False
            return matches

    def get_selected_leagues(self):
        """الحصول على الدوريات المختارة من قاعدة البيانات SQLite"""
        try:
            # استخدام قاعدة البيانات SQLite بدلاً من connection القديم
            return self.db.get_selected_leagues()
        except Exception as e:
            print(f"❌ Error getting selected leagues: {e}")
            return []

    def save_calendar_filter_state(self):
        try:
            selected_leagues = self.get_selected_leagues()
            
            filter_state = {
                'active': self.calendar_filter_active,
                'type': self.calendar_filter_type,
                'selected_leagues_count': len(selected_leagues),
                'last_updated': datetime.now().isoformat()
            }
            
            filter_file = os.path.join(self.calendar_filter_dir, 'filter_state.json')
            with open(filter_file, 'w', encoding='utf-8') as f:
                json.dump(filter_state, f, indent=2)
                
            print(f"💾 Saved filter state: {len(selected_leagues)} selected leagues")
                
        except Exception as e:
            print(f"❌ Error saving filter state: {e}")

    def load_calendar_filter_state(self):
        try:
            filter_file = os.path.join(self.calendar_filter_dir, 'filter_state.json')
            if os.path.exists(filter_file):
                with open(filter_file, 'r', encoding='utf-8') as f:
                    filter_state = json.load(f)
                
                self.calendar_filter_active = filter_state.get('active', False)
                self.calendar_filter_type = filter_state.get('type', 'perfect_1_1')
                
                selected_count = filter_state.get('selected_leagues_count', 0)
                print(f"📅 Loaded calendar filter: Active={self.calendar_filter_active}, Type={self.calendar_filter_type}, Selected leagues={selected_count}")
                
        except Exception as e:
            print(f"❌ Error loading filter state: {e}")
            self.calendar_filter_active = False
            self.calendar_filter_type = 'perfect_1_1'

    def toggle_calendar_filter(self):
        self.calendar_filter_active = not self.calendar_filter_active
        
        # حفظ حالة الفلتر
        self.save_calendar_filter_state()
        
        status = "ACTIVATED" if self.calendar_filter_active else "DEACTIVATED"
        filter_type_display = self.calendar_filter_type.replace('_', ' ').title()
        
        self.show_snackbar(f"📅 Calendar Filter {status} ({filter_type_display})")
        
        # إذا كنا في وضع التقويم، نعيد تحميل المباريات مباشرة
        if self.calendar_mode and self.current_calendar_date:
            Clock.schedule_once(lambda dt: self.show_calendar_matches(self.current_calendar_date), 0.2)
        
        # تحديث واجهة البروفايل إذا كنا فيها
        if self.current_tab == 'profile':
            Clock.schedule_once(lambda dt: self.show_profile(), 0.3)

    def set_calendar_filter_type(self, filter_type):
        """تعيين نوع فلتر التقويم مع التحقق من الصحة"""
        valid_filters = ['perfect_1_1']
        if filter_type not in valid_filters:
            self.show_snackbar(f"❌ Invalid filter type: {filter_type}")
            return
            
        self.calendar_filter_type = filter_type
        self.save_calendar_filter_state()
        
        filter_type_display = filter_type.replace('_', ' ').title()
        self.show_snackbar(f"📅 Calendar filter type set to: {filter_type_display}")
        
        # إذا كان الفلتر نشطاً، نقوم بتحديث العرض
        if self.calendar_filter_active and self.calendar_mode:
            self.show_snackbar("🔄 Applying new filter type...")
            self.show_calendar_matches(self.current_calendar_date)

    # ===========================================
    # END OF CALENDAR FILTER FUNCTIONS
    # ===========================================

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
                    return live_matches
            return []
                
        except Exception:
            return []

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
            self.matches = matches
            self.today_matches = [m for m in matches if self._is_today(m.get('time'))]
            self.api_available = True
            
            if self.current_tab == 'live' and not self.calendar_mode:
                pass 
                    
            self.show_snackbar(f"Loaded {len(matches)} live matches")
            
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

        final_matches_to_show = self.get_matches_without_favorites_and_hidden(filtered_live_matches)
        
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
        fav_matches_data = [m for m in all_available_matches if self.is_favorite(m.get('id'))]
        
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
        
        # حفظ في قاعدة البيانات
        for league in current_selected:
            self.db.add_selected_league(league['id'], league['name'], league)

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
        
        # ===========================================
        # CALENDAR FILTER CONTROL SECTION - ADDED
        # ===========================================
        calendar_filter_header = OneLineListItem(text="📅 CALENDAR FILTER SYSTEM (NS Matches Only)")
        calendar_filter_header.md_bg_color = get_color_from_hex("#E1F5FE")
        container.add_widget(calendar_filter_header)

        calendar_filter_box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(150))

        # حالة الفلتر الحالية
        filter_status = "✅ ACTIVE" if self.calendar_filter_active else "❌ INACTIVE"
        filter_status_color = "#4CAF50" if self.calendar_filter_active else "#F44336"
        filter_type_display = self.calendar_filter_type.replace('_', ' ').title()

        status_label = MDBoxLayout(
            orientation='vertical',
            spacing=dp(2),
            size_hint_y=None,
            height=dp(40)
        )

        status_label.add_widget(MDLabel(
            text=f"Calendar Filter: {filter_status}",
            theme_text_color='Custom',
            text_color=get_color_from_hex(filter_status_color),
            halign='center',
            bold=True
        ))

        status_label.add_widget(MDLabel(
            text=f"Type: {filter_type_display}",
            theme_text_color='Secondary',
            halign='center',
            font_style='Caption'
        ))

        calendar_filter_box.add_widget(status_label)

        # أزرار التحكم
        btn_calendar_row = MDBoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(40))

        btn_toggle_calendar = MDRaisedButton(
            text="✅ Activate" if not self.calendar_filter_active else "❌ Deactivate",
            on_release=lambda x: self.toggle_calendar_filter(),
            size_hint_x=0.5,
            md_bg_color=get_color_from_hex("#4CAF50" if not self.calendar_filter_active else "#F44336")
        )

        btn_calendar_row.add_widget(btn_toggle_calendar)
        calendar_filter_box.add_widget(btn_calendar_row)

        container.add_widget(calendar_filter_box)
        # ===========================================
        # END OF CALENDAR FILTER SECTION
        # ===========================================
        
        filter_header = OneLineListItem(text="🎯 ADVANCED FILTER SYSTEM")
        filter_header.md_bg_color = get_color_from_hex("#E1F5FE")
        container.add_widget(filter_header)
        
        filter_buttons_box = MDBoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(200))
        
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
            
            # حفظ في قاعدة البيانات
            for league in selected:
                self.db.add_selected_league(league['id'], league['name'], league)

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
            

            losing_stats_str = self.fetch_team_last_matches(
                losing_team_id, league_id, season, losing_is_home
            )
            
            winning_stats_str = self.fetch_team_last_matches(
                winning_team_id, league_id, season, not losing_is_home
            )
            

            losing_goals_for, losing_goals_against = self.extract_goals_for_and_against(losing_stats_str)
            winning_goals_for, winning_goals_against = self.extract_goals_for_and_against(winning_stats_str)
            

            if losing_goals_against > 7:
                return "❌ no (الخاسر استقبل أكثر من 7 أهداف)"
            

            if (losing_goals_against - winning_goals_against) > 4:
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
                
                # الحصول على IDs المخفية من الكاش
                hidden_ids = self.get_hidden_match_ids()
                
                for match in relevant_matches:
                    match_id = str(match.get('id'))
                    
                    # استبعاد المباريات المخفية
                    if match_id in hidden_ids:
                        continue
                    
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
            
        final_filtered_matches = self.get_matches_without_favorites_and_hidden(self.filtered_matches)
            
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

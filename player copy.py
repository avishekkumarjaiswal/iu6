import streamlit as st
import sqlite3
import pandas as pd
import json
import time
from datetime import datetime
from PIL import Image
import base64

# Set up the Streamlit page (must be the first command)
st.set_page_config(layout="wide")  # Use the full width of the screen

# Hide Streamlit menu, footer, and prevent code inspection
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none !important;}  /* Hide GitHub button */
    </style>

    <script>
    document.addEventListener('contextmenu', event => event.preventDefault());
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;  // Disable "Ctrl + U" (View Source) & "Ctrl + S" (Save As)
        }
        if (e.keyCode == 123) {
            return false;  // Disable "F12" (DevTools)
        }
    };
    </script>
    """, unsafe_allow_html=True)

# Add these functions near the top after imports and before the main app code
def get_current_hints(level):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hints FROM questions WHERE level = ?", (level,))
    result = cursor.fetchone()
    conn.close()
    return json.loads(result[0]) if result else []

def show_hints_section(hints, current_level):
    # Display hints if available
    if hints:
        for i, hint in enumerate(hints):
            if hint and str(hint).lower() != "nan":
                if hint.startswith("http"):
                    st.markdown(f"""
                        <div class="hint-link-preview">
                            <a href="{hint}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="hint-link-title">Hint {i + 1} - Click to open</div>
                                <div class="hint-link-url">{hint}</div>
                            </a>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="hint-item">
                            <strong>Hint {i + 1}:</strong> {hint}
                        </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("No hints available for this level.")
    
    # Add a timestamp for the last update
    st.markdown(f"""
        <div style='text-align: right; padding: 5px; font-size: 12px; color: #666;'>
            🔄 Hints updated: {time.strftime('%H:%M:%S')}
        </div>
    """, unsafe_allow_html=True)

def update_game_leaderboard(leaderboard_container, player_stats_container):
    df = get_current_leaderboard()
    if df is not None:
        # Format the leaderboard display
        display_df = df.copy()
        display_df["Rank"] = display_df["Position"].apply(lambda x: f"#{x}")
        
        # Add medal emojis for top 3
        def get_medal(position):
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            return medals.get(position, "")
        
        display_df["Player"] = display_df.apply(
            lambda row: f"{get_medal(row['Position'])} {row['Username']}"
            if row['Position'] <= 3
            else row['Username'],
            axis=1
        )
        
        # Create a view for display
        view_df = display_df[["Rank", "Player", "Round"]]
        
        # Highlight current user
        def highlight_user(row):
            player_name = row["Player"].replace("🥇 ", "").replace("🥈 ", "").replace("🥉 ", "")
            if player_name == st.session_state.username:
                return ['background-color: #2D2D2D; color: #FFFFFF'] * len(row)
            return [''] * len(row)
        
        # Style and display the main leaderboard
        styled_df = (view_df.style
                   .apply(highlight_user, axis=1)
                   .set_properties(**{
                       'text-align': 'center',
                       'font-size': '14px',
                       'padding': '8px'
                   }))
        
        with leaderboard_container:
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=min(400, len(df) * 35 + 38)
            )
        
        # Show current player stats
        user_data = df[df["Username"] == st.session_state.username]
        with player_stats_container:
            if not user_data.empty:
                position = user_data.iloc[0]["Position"]
                level = user_data.iloc[0]["Round"]
                total_players = len(df)
                percentile = round((position/total_players)*100)
                
                medal = get_medal(position)
                rank_display = f"{medal} #{position}" if medal else f"#{position}"
                
                st.markdown(f"""
                    <div style='background: #2D2D2D; padding: 15px; border-radius: 10px; text-align: center;'>
                        <div style='font-size: 24px; margin-bottom: 10px;'>Your Stats</div>
                        <div style='font-size: 18px; margin: 5px 0;'>Rank: {rank_display}</div>
                        <div style='font-size: 18px; margin: 5px 0;'>Round: {level}</div>
                        <div style='font-size: 14px; color: #888;'>
                            Top {percentile}% of players
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div style='background: #2D2D2D; padding: 15px; border-radius: 10px; text-align: center;'>
                        <div style='font-size: 18px;'>Complete a level to appear on the leaderboard!</div>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style='text-align: right; padding: 5px; font-size: 12px; color: #666;'>
                🔄 Last updated: {time.strftime('%H:%M:%S')}
            </div>
        """, unsafe_allow_html=True)

def admin_page():
    inject_custom_css()

    st.title("Admin Panel")

    # Main container for layout
    st.markdown('<div class="main-container">', unsafe_allow_html=True)

    # Sidebar for CRUD operations
    st.sidebar.markdown('<div class="sidebar">', unsafe_allow_html=True)
    st.sidebar.write("### CRUD Operations")

    # Load all questions and players
    questions = load_questions()
    players = load_players()

    # CRUD operations dropdown
    crud_option = st.sidebar.selectbox("Select Operation", ["Add", "Update", "Delete", "Manage Players"])

    # Add new question
    if crud_option == "Add":
        st.sidebar.write("### Add New Question")
        with st.sidebar.form("add_question_form"):
            level = st.number_input("Round", min_value=0, step=0)
            question = st.text_area("Question")
            answer = st.text_input("Answer")
            hint1 = st.text_input("Hint 1")
            hint2 = st.text_input("Hint 2")
            hint3 = st.text_input("Hint 3")
            image_url = st.text_input("Image URL (optional)")  # New field for image URL
            if st.form_submit_button("Add Question"):
                hints = json.dumps([hint1, hint2, hint3])
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO questions (level, question, answer, hints, image_url)
                    VALUES (?, ?, ?, ?, ?)
                """, (level, question, answer, hints, image_url))
                conn.commit()
                conn.close()
                st.success("Question added successfully!")
                st.rerun()

    # Update question
    elif crud_option == "Update":
        st.sidebar.write("### Update Question")
        levels = [q[0] for q in questions]
        if levels:
            level_to_update = st.sidebar.selectbox("Select Round to Update", levels)
            selected_question = next((q for q in questions if q[0] == level_to_update), None)
            if selected_question:
                question = selected_question[1]
                answer = selected_question[2]
                hints = json.loads(selected_question[3])
                hint1 = hints[0] if len(hints) > 0 else ""
                hint2 = hints[1] if len(hints) > 1 else ""
                hint3 = hints[2] if len(hints) > 2 else ""
                image_url = selected_question[4] if len(selected_question) > 4 else ""  # Existing image URL

                with st.sidebar.form("update_question_form"):
                    new_question = st.text_area("Question", value=question)
                    new_answer = st.text_input("Answer", value=answer)
                    new_hint1 = st.text_input("Hint 1", value=hint1)
                    new_hint2 = st.text_input("Hint 2", value=hint2)
                    new_hint3 = st.text_input("Hint 3", value=hint3)
                    new_image_url = st.text_input("Image URL (optional)", value=image_url)  # Update image URL
                    if st.form_submit_button("Update Question"):
                        new_hints = json.dumps([new_hint1, new_hint2, new_hint3])
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE questions 
                            SET question = ?, answer = ?, hints = ?, image_url = ?
                            WHERE level = ?
                        """, (new_question, new_answer, new_hints, new_image_url, level_to_update))
                        conn.commit()
                        conn.close()
                        st.success(f"Question for Round {level_to_update} updated successfully!")
                        st.rerun()
        else:
            st.sidebar.info("No questions available to update.")

    # Delete question
    elif crud_option == "Delete":
        st.sidebar.write("### Delete Question")
        levels = [q[0] for q in questions]
        if levels:
            level_to_delete = st.sidebar.selectbox("Select Round to Delete", levels)
            if st.sidebar.button("Delete Question"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM questions WHERE level = ?", (level_to_delete,))
                conn.commit()
                conn.close()
                st.success(f"Question for Round {level_to_delete} deleted successfully!")
                st.rerun()
        else:
            st.sidebar.info("No questions available to delete.")

    # Manage players
    elif crud_option == "Manage Players":
        st.sidebar.write("### Manage Players")
        if players:
            players_df = pd.DataFrame(players, columns=["Username", "Round"])
            st.sidebar.write("#### Registered Players")
            st.sidebar.table(players_df)

            player_to_manage = st.sidebar.selectbox("Select Player", [p[0] for p in players])
            col1, col2 = st.sidebar.columns(2)
            
            with col1:
                if st.button("Delete Player"):
                    if delete_player(player_to_manage):
                        st.success(f"Player {player_to_manage} deleted successfully!")
                        st.rerun()
                    
            with col2:
                if st.button("Reset Progress"):
                    if reset_player_progress(player_to_manage):
                        st.success(f"Progress reset for {player_to_manage}!")
                        st.rerun()
        else:
            st.sidebar.info("No players registered yet.")

    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    # Main content for questions
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    st.write("### All Questions")
    if questions:
        # Ensure all rows have 5 columns (Round, Question, Answer, Hints, Image URL)
        questions_with_image = []
        for q in questions:
            if len(q) == 4:  # If image_url is missing
                q = list(q) + [None]  # Add None for image_url
            questions_with_image.append(q)
        
        # Create DataFrame
        questions_df = pd.DataFrame(questions_with_image, columns=["Round", "Question", "Answer", "Hints", "Image URL"])
        st.table(questions_df)
    else:
        st.info("No questions found in the database.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Logout button
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# Hide Streamlit menu, footer, and prevent code inspection
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none !important;}  /* Hide GitHub button */
    </style>

    <script>
    document.addEventListener('contextmenu', event => event.preventDefault());
    document.onkeydown = function(e) {
        if (e.ctrlKey && (e.keyCode === 85 || e.keyCode === 83)) {
            return false;  // Disable "Ctrl + U" (View Source) & "Ctrl + S" (Save As)
        }
        if (e.keyCode == 123) {
            return false;  // Disable "F12" (DevTools)
        }
    };
    </script>
    """, unsafe_allow_html=True)

# Constants
DATABASE_FILE = "cryptic_hunt2025.db"
QUESTIONS_CSV = "questions.csv"
ADMIN_PASSWORD = "admin2025"  # Replace with a secure password in production

# Initialize SQLite database and create tables
def initialize_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            level INTEGER DEFAULT 0
        )
    """)

    # Create questions table with level starting from 0
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level INTEGER UNIQUE NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            hints TEXT,
            image_url TEXT  -- New column for image URL
        )
    """)

    # Create leaderboard table with auto-updating timestamp
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            level INTEGER NOT NULL,
            timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime'))
        )
    """)

    # Create a table to track last update
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS last_update (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime'))
        )
    """)

    # Insert initial last_update record if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO last_update (id) VALUES (1)
    """)

    # Create trigger to update last_update timestamp
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_leaderboard_timestamp
        AFTER INSERT ON leaderboard
        BEGIN
            UPDATE last_update 
            SET timestamp = strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')
            WHERE id = 1;
        END
    """)

    conn.commit()
    conn.close()

# Load questions from CSV and insert into the database
def load_questions_from_csv():
    try:
        df = pd.read_csv(QUESTIONS_CSV)
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        for _, row in df.iterrows():
            level = row["Round"]
            question = row["Question"]
            answer = row["Answer"]
            hints = json.dumps([row[f"Hint{i+1}"] for i in range(3) if f"Hint{i+1}" in row])

            cursor.execute("""
                INSERT OR IGNORE INTO questions (level, question, answer, hints)
                VALUES (?, ?, ?, ?)
            """, (level, question, answer, hints))

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error loading questions from CSV: {str(e)}")

# Initialize the database and load questions from CSV
initialize_db()
load_questions_from_csv()

# Database connection
def get_db_connection():
    return sqlite3.connect(DATABASE_FILE, check_same_thread=False)

# Load questions from the database
def load_questions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT level, question, answer, hints, image_url FROM questions ORDER BY level")
    questions = cursor.fetchall()
    conn.close()
    return questions

# Load leaderboard from the database (only latest entry per user)
def load_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username, MAX(level) as level, MIN(timestamp) as timestamp 
        FROM leaderboard 
        GROUP BY username 
        ORDER BY level DESC, timestamp ASC
    """)
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard

# Get player's current rank
def get_player_rank(username):
    leaderboard = load_leaderboard()
    for rank, entry in enumerate(leaderboard, start=1):
        if entry[0] == username:
            return rank
    return None

# Update user progress in the database
def update_user_progress(username, level):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update user's level
    cursor.execute("UPDATE users SET level = ? WHERE username = ?", (level, username))
    
    # Add new leaderboard entry (trigger will update last_update timestamp)
    cursor.execute("""
        INSERT INTO leaderboard (username, level)
        VALUES (?, ?)
    """, (username, level))
    
    conn.commit()
    conn.close()

# Check user credentials
def authenticate_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

# Register a new user
def register_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

# Add missing load_players function
def load_players():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, level FROM users ORDER BY level DESC")
    players = cursor.fetchall()
    conn.close()
    return players

# Add missing delete_player function
def delete_player(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        cursor.execute("DELETE FROM leaderboard WHERE username = ?", (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting player: {e}")
        return False
    finally:
        conn.close()

# Add missing reset_player_progress function
def reset_player_progress(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET level = 0 WHERE username = ?", (username,))
        cursor.execute("DELETE FROM leaderboard WHERE username = ?", (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error resetting player progress: {e}")
        return False
    finally:
        conn.close()

# Add these functions near the top after imports
def get_latest_update_timestamp():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp FROM last_update WHERE id = 1")
    timestamp = cursor.fetchone()[0]
    conn.close()
    return timestamp

def get_current_leaderboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get latest level and position for each user
    cursor.execute("""
        WITH UserRounds AS (
            SELECT 
                username,
                level,
                timestamp,
                ROW_NUMBER() OVER (PARTITION BY username ORDER BY level DESC, timestamp ASC) as rn
            FROM leaderboard
        )
        SELECT 
            username,
            level,
            timestamp,
            ROW_NUMBER() OVER (ORDER BY level DESC, timestamp ASC) as position
        FROM UserRounds
        WHERE rn = 1
        ORDER BY level DESC, timestamp ASC
    """)
    
    leaderboard = cursor.fetchall()
    conn.close()
    
    if leaderboard:
        df = pd.DataFrame(leaderboard, columns=["Username", "Round", "Timestamp", "Position"])
        return df
    return None

# Update inject_custom_css function
def inject_custom_css():
    st.markdown(
        """
        <style>
        /* Dark mode theme colors */
        :root {
            --bg-color: #1E1E1E;
            --card-bg: #FFFFFF;  /* White background for cards */
            --text-color-dark: #000000;  /* Black text for cards */
            --text-color-light: #FFFFFF;  /* White text for dark areas */
            --border-color: #404040;
            --input-bg: #FFFFFF;  /* White background for input */
            --button-bg: #4A4A4A;
            --button-hover: #5A5A5A;
        }

        /* Global dark mode styles */
        body {
            background-color: var(--bg-color);
            color: var(--text-color-light);
        }

        /* Question card styling */
        .question-card {
            background: var(--card-bg);
            border-radius: 25px;
            padding: 30px;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
            color: var(--text-color-dark);  /* Black text for question card */
        }

        .level-title {
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 20px;
            color: var(--text-color-dark);  /* Black text for title */
        }

        .question-text {
            font-size: 16px;
            line-height: 1.6;
            color: var(--text-color-dark);  /* Black text for question */
            margin-bottom: 25px;
        }

        /* Navigation buttons */
        .nav-buttons {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1001; /* Above sidebar */
        }

        .nav-button {
            background: var(--card-bg);  /* White background for buttons */
            border: none;
            border-radius: 15px;
            padding: 8px 16px;
            font-size: 14px;
            cursor: pointer;
            color: var(--text-color-dark);  /* Black text for buttons */
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
            transition: background-color 0.3s ease;
        }

        .nav-button:hover {
            background-color: #F0F0F0;  /* Slightly darker white on hover */
        }

        /* Answer input styling */
        .stTextInput input {
            border-radius: 2px;
            border: 1px solid #DDD;
            padding: 10px 20px;
            margin-top: 0px;
            width: 100%;
            font-size: 16px;
            background-color: var(--input-bg);  /* White background */
            color: var(--text-color-dark);  /* Black text */
        }

        .stTextInput input:focus {
            border-color: #666;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
        }

        /* Submit button styling */
        .stButton button {
            background-color: var(--button-bg);
            color: var(--text-color-light);  /* White text for submit button */
            border: none;
            border-radius: 20px;
            padding: 10px 20px;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }

        .stButton button:hover {
            background-color: var(--button-hover);
        }

        /* Dark mode for Streamlit elements */
        .stApp {
            background-color: var(--bg-color);
        }

        .stMarkdown {
            color: var(--text-color-light);  /* White text for markdown */
        }

        .stAlert {
            background-color: var(--bg-color);
            color: var(--text-color-light);  /* White text for alerts */
            border: 1px solid var(--border-color);
        }

        /* Labels and other text */
        label {
            color: var(--text-color-light) !important;  /* White text for labels */
        }

        /* Hide Streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stDeployButton {display: none !important;}

        /* Title styling */
        h1 {
            color: var(--text-color-light) !important;  /* Force white color for main title */
        }

        /* Hint button styling */
        .nav-button[onclick*="show_hints"] {
            position: relative;
            transition: all 0.3s ease;
        }

        .nav-button[onclick*="show_hints"]:hover {
            background-color: #F0F0F0;
        }

        .nav-button[onclick*="show_hints"].active {
            background-color: #E0E0E0;
        }

        /* Hint section animation */
        #hint-section {
            transition: all 0.3s ease;
            overflow: hidden;
        }

        /* Hint styling */
        .hints-container {
            margin: 20px 0;
            padding: 15px;
            background: rgba(0, 0, 0, 0.05);
            border-radius: 10px;
        }

        .hint-item {
            padding: 12px 15px;
            margin: 8px 0;
            background: white;
            border-radius: 8px;
            color: black;
            font-size: 14px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        /* Hint sidebar styling */
        .hint-sidebar {
            position: fixed;
            right: -300px; /* Start hidden */
            top: 0;
            width: 300px;
            height: 100vh;
            background: var(--bg-color);
            padding: 20px;
            box-shadow: -2px 0 5px rgba(0, 0, 0, 0.2);
            transition: right 0.3s ease;
            z-index: 1000;
            overflow-y: auto; /* Enable scrolling if needed */
        }

        .hint-sidebar.show {
            right: 0;
        }

        .hint-sidebar-title {
            color: var(--text-color-light);
            font-size: 24px;
            margin-bottom: 20px;
            padding-top: 60px; /* Space for nav buttons */
        }

        .hints-container {
            margin: 20px 0;
        }

        .hint-item {
            padding: 12px 15px;
            margin: 8px 0;
            background: white;
            border-radius: 8px;
            color: black;
            font-size: 14px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        /* Active state for hint button */
        .nav-button[data-action="hints"].active {
            background-color: #E0E0E0;
        }

        /* Update nav buttons to stay on top */
        .nav-buttons {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1001; /* Above sidebar */
        }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            background-color: #1E1E1E;
        }

        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 0px 16px;
            background-color: #2D2D2D;
            border-radius: 4px 4px 0px 0px;
            color: #FFFFFF;
            border: none;
        }

        .stTabs [aria-selected="true"] {
            background-color: #4A4A4A;
        }

        /* Embedded link preview */
        .hint-link-preview {
            background: #2D2D2D;
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
            border: 1px solid #404040;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .hint-link-preview:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }

        .hint-link-title {
            color: #FFFFFF;
            font-size: 14px;
            margin-bottom: 4px;
        }

        .hint-link-url {
            color: #888888;
            font-size: 12px;
            word-break: break-all;
        }

        /* Auto-refresh indicator */
        .refresh-indicator {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 12px;
            z-index: 1000;
        }

        /* Sidebar styling */
        .css-1d391kg {  /* Sidebar class */
            background-color: #1E1E1E;
            padding: 1rem;
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            background-color: #2D2D2D !important;
            border-radius: 5px;
        }

        .streamlit-expanderContent {
            background-color: #1E1E1E;
            border: 1px solid #2D2D2D;
            border-radius: 0 0 5px 5px;
        }

        /* Hint link preview in sidebar */
        .hint-link-preview {
            background: #2D2D2D;
            border-radius: 8px;
            padding: 8px;
            margin: 4px 0;
            border: 1px solid #404040;
        }

        /* Leaderboard styling */
        .stDataFrame {
            background-color: #1E1E1E !important;
            border-radius: 10px !important;
            overflow: hidden !important;
        }

        .stDataFrame td {
            font-size: 14px !important;
            text-align: center !important;
        }

        .stDataFrame th {
            background-color: #2D2D2D !important;
            color: white !important;
            text-align: center !important;
            font-weight: bold !important;
        }

        /* Player stats card */
        .player-stats {
            background: #2D2D2D;
            border-radius: 10px;
            padding: 15px;
            margin-top: 10px;
        }

        /* Medal animations */
        @keyframes shine {
            0% { opacity: 0.5; }
            50% { opacity: 1; }
            100% { opacity: 0.5; }
        }

        .medal {
            animation: shine 2s infinite;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Create two columns
col1, col2 = st.columns([3, 1])  # Adjust the ratio as needed

# Add the title to the first column
with col1:
    st.markdown("<h1 style='color: white;'>IDEATION UNLOCK 6.0: UNLOCK THE VAULT</h1>", unsafe_allow_html=True)

# Add the image to the second column
with col2:
    image_url = "https://i.postimg.cc/ydqznqVn/logoquiz.png"  # Replace with your image URL
    st.image(image_url, width=158)  # Adjust the width as needed

# Session state for user authentication and mode
if "username" not in st.session_state:
    st.session_state.username = None
if "level" not in st.session_state:
    st.session_state.level = 0
if "hints_revealed" not in st.session_state:
    st.session_state.hints_revealed = {}  # Track revealed hints for each level

# Main page (name entry)
if st.session_state.username is None:
    # Show leaderboard first
    st.markdown("### 🏆 Live Leaderboard")
    main_leaderboard_container = st.container()
    
    with main_leaderboard_container:
        df = get_current_leaderboard()
        if df is not None:
            # Format the leaderboard display
            display_df = df.copy()
            display_df["Rank"] = display_df["Position"].apply(lambda x: f"#{x}")
            
            # Add medal emojis for top 3
            def get_medal(position):
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                return medals.get(position, "")
            
            display_df["Player"] = display_df.apply(
                lambda row: f"{get_medal(row['Position'])} {row['Username']}"
                if row['Position'] <= 3
                else row['Username'],
                axis=1
            )
            
            # Create a view for display
            view_df = display_df[["Rank", "Player", "Round"]]
            
            # Style the dataframe
            styled_df = (view_df.style
                       .set_properties(**{
                           'text-align': 'center',
                           'font-size': '14px',
                           'padding': '8px',
                           'background-color': '#2D2D2D'
                       }))
            
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=min(400, len(df) * 35 + 38)
            )
            
            st.markdown(f"""
                <div style='text-align: right; padding: 5px; font-size: 12px; color: #666;'>
                    🔄 Last updated: {time.strftime('%H:%M:%S')}
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No players on the leaderboard yet. Be the first to play!")

    # Add some space between leaderboard and name entry section
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Create tabs for player login and admin login
    tab1, tab2 = st.tabs(["Play Game", "Admin Login"])
    
    with tab1:
        # Name entry section
        st.subheader("Enter Your Name to Play")
        username = st.text_input("Your Name", key="name_input")
        
        if st.button("Start Playing"):
            if username.strip():
                st.session_state.username = username.strip()
                
                # Check if this is a new player or returning player
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Check if player exists
                cursor.execute("SELECT level FROM users WHERE username = ?", (st.session_state.username,))
                result = cursor.fetchone()
                
                if result:
                    # Existing player - load their progress
                    st.session_state.level = result[0]
                else:
                    # New player - create entry
                    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                                 (st.session_state.username, "dummy_password"))
                    conn.commit()
                    st.session_state.level = 0
                
                conn.close()
                st.rerun()
            else:
                st.error("Please enter a name to continue")
    
    with tab2:
        # Admin login section
        st.subheader("Admin Access")
        admin_username = st.text_input("Admin Username", key="admin_username")
        admin_password = st.text_input("Admin Password", type="password", key="admin_password")
        if st.button("Admin Login"):
            if admin_username == "admin" and admin_password == ADMIN_PASSWORD:
                st.session_state.username = "admin"
                st.session_state.is_admin = True
                st.success("Welcome, Admin!")
                time.sleep(1)  # Add a small delay to avoid flickering
                st.rerun()
            else:
                st.error("Invalid admin credentials.")

    # Auto-refresh for main page leaderboard
    time.sleep(2)
    st.rerun()

# Player's game page
elif st.session_state.username and not st.session_state.get("is_admin", False):
    inject_custom_css()
    
    questions = load_questions()
    current_level = st.session_state.level

    # Main content area for question
    if current_level < len(questions):
        question_data = questions[current_level]
        hints = json.loads(question_data[3])
        image_url = question_data[4] if len(question_data) > 4 else None

        # Question card in main area
        st.markdown(f"""
            <div class="question-card">
                <div class="level-title">Round {question_data[0]}</div>
                <div class="question-text">{question_data[1]}</div>
        """, unsafe_allow_html=True)

        # Display image if URL is provided
        if image_url:
            st.markdown("""
                <style>
                .question-image {
                    max-width: 100%;
                    height: 200px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }
                </style>
            """, unsafe_allow_html=True)
            st.markdown(f'<img src="{image_url}" class="question-image" alt="Question Image">', unsafe_allow_html=True)

        st.markdown("""
            <div class="answer-section">
                <label>Your answer:</label>
            </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Answer input
        answer = st.text_input("", key="answer_input", label_visibility="collapsed")
        if st.button("Submit"):
            if answer.lower() == question_data[2].lower():
                update_user_progress(st.session_state.username, current_level + 1)
                st.session_state.level += 1
                st.rerun()
            else:
                st.error("Submit correct answer to progress next level!")

        # Sidebar content
        with st.sidebar:
            st.markdown(f"### Player: {st.session_state.username}")
            
            # Hints Section
            with st.expander("🎯 Hints", expanded=True):
                show_hints_section(hints, current_level)

            # Add separator
            st.markdown("<hr>", unsafe_allow_html=True)

            # Leaderboard Section
            st.markdown("### 🏆 Live Leaderboard")
            
            # Create two columns for the leaderboard
            left_col, right_col = st.columns([2, 1])
            
            with left_col:
                leaderboard_container = st.empty()
            
            with right_col:
                player_stats_container = st.empty()

            # Update leaderboard display
            update_game_leaderboard(leaderboard_container, player_stats_container)

            # Logout button
            if st.button("Change Name"):
                st.session_state.clear()
                st.rerun()

            # Auto-refresh
            time.sleep(1)
            st.rerun()

    else:
        # Quiz Completed Section
        st.markdown("""
            <style>
            .quiz-completed {
                text-align: center;
                padding: 50px;
                background: #2D2D2D;
                border-radius: 15px;
                margin: 20px 0;
            }
            .quiz-completed h1 {
                font-size: 48px;
                color: #4CAF50;
                margin-bottom: 20px;
            }
            .quiz-completed p {
                font-size: 24px;
                color: #FFFFFF;
            }
            </style>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="quiz-completed">
                <h1>🎉 Quiz Completed! 🎉</h1>
                <p>Congratulations {st.session_state.username}, you've answered all the questions!</p>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("Play Again with Different Name"):
            st.session_state.clear()
            st.rerun()

# Admin page
elif st.session_state.username == "admin" and st.session_state.get("is_admin", False):
    admin_page()

# Initialize session state for current_level
if "level" not in st.session_state:
    st.session_state.level = 0  # Default starting level

# Ensure questions are loaded
questions = load_questions()  # Assuming this function loads the questions from the database

# Check if current_level is within the valid range
if st.session_state.level < len(questions):
    question_data = questions[st.session_state.level]  # Extract the current question data
    image_url = question_data[4] if len(question_data) > 4 else None  # Extract image_url

    # Display image if URL is provided
    if image_url:
        st.markdown("""
            <style>
            .image-container {
                display: flex;
                justify-content: center; /* Center horizontally */
                align-items: center; /* Center vertically */
                width: 100%;
                height: 200px; /* Fixed height */
                overflow: hidden; /* Hide overflow */
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .question-image {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain; /* Maintain aspect ratio */
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.markdown(
            f'<div class="image-container">'
            f'<img src="{image_url}" class="question-image" alt="Question Image">'
            f'</div>',
            unsafe_allow_html=True
        )

    # Display the question and answer input
    st.markdown(f"""
        <div class="question-card">
            <div class="level-title">Round {question_data[0]}</div>
            <div class="question-text">{question_data[1]}</div>
            <div class="answer-section">
                <label>Your answer:</label>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Answer input
    answer = st.text_input("", key="answer_input", label_visibility="collapsed")
    if st.button("Submit"):
        if answer.lower() == question_data[2].lower():
            update_user_progress(st.session_state.username, st.session_state.level + 1)
            st.session_state.level += 1
            st.rerun()
        else:
            st.error("Submit correct answer to progress to the next level!")

else:
    # Quiz Completed Section
    st.markdown("""
        <style>
        .quiz-completed {
            text-align: center;
            padding: 50px;
            background: #2D2D2D;
            border-radius: 15px;
            margin: 20px 0;
        }
        .quiz-completed h1 {
            font-size: 48px;
            color: #4CAF50;
            margin-bottom: 20px;
        }
        .quiz-completed p {
            font-size: 24px;
            color: #FFFFFF;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="quiz-completed">
            <h1>🎉 Quiz Completed! 🎉</h1>
            <p>Congratulations, you've answered all the questions!</p>
        </div>
    """, unsafe_allow_html=True)
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# ========================= GEMINI AI SETTINGS ========================= #
GEMINI_API_KEY = "AIzaSyBzlYP2vYLwsJq8BOR8e5i1jHffVydbQoE"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

def generate_review(prompt):
    """Generates a product review using Google Gemini AI."""
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(GEMINI_URL, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except KeyError:
            return "AI generation failed. Please try again."
    else:
        return f"Error: {response.status_code}, {response.text}"

def generate_summary(reviews):
    """Generates a summary of the top 5 reviews using Google Gemini AI."""
    prompt = "Summarize the following reviews in 2-3 lines:\n\n"
    for review in reviews[:5]:
        prompt += f"Review: {review['Review']}\n\n"

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(GEMINI_URL, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except KeyError:
            return "AI generation failed. Please try again."
    else:
        return f"Error: {response.status_code}, {response.text}"

# ========================= DATABASE FUNCTIONS ========================= #
def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect("amazon_reviews.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            overall_rating TEXT,
            review_title TEXT,
            author TEXT,
            review_date TEXT,
            rating TEXT,
            review TEXT
        )
    ''')
    conn.commit()
    conn.close()

def store_review(product_name, review):
    """Stores a review in the database."""
    conn = sqlite3.connect("amazon_reviews.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reviews (product_name, overall_rating, review_title, author, review_date, rating, review)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (product_name, "AI Generated", "Generated Review", "AI Model", "2024-03-01", "5 stars", review))
    conn.commit()
    conn.close()

def fetch_reviews(product_name):
    """Fetches reviews from the database."""
    conn = sqlite3.connect("amazon_reviews.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE product_name = ?", (product_name,))
    reviews = cursor.fetchall()
    conn.close()
    return reviews

# ========================= AMAZON SCRAPER ========================= #
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def get_amazon_reviews(url, max_reviews=10):
    """Scrapes product reviews from an Amazon product page."""
    try:
        parsed_url = urlparse(url)
        if "amazon" not in parsed_url.netloc:
            return {"error": "Invalid Amazon URL"}

        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            return {"error": f"Failed to fetch data. Status code: {response.status_code}"}

        soup = BeautifulSoup(response.text, "html.parser")
        product_title = soup.select_one("#productTitle")
        product_title = product_title.get_text(strip=True) if product_title else "Unknown Product"
        rating = soup.select_one(".a-icon-alt")
        rating = rating.get_text(strip=True) if rating else "No rating"
        reviews = soup.select(".review")

        review_data = []
        for review in reviews[:max_reviews]:
            review_title = review.select_one(".review-title")
            review_author = review.select_one(".a-profile-name")
            review_date = review.select_one(".review-date")
            review_text = review.select_one(".review-text-content span")
            review_rating = review.select_one(".review-rating")

            review_data.append({
                "Title": review_title.get_text(strip=True) if review_title else "No Title",
                "Author": review_author.get_text(strip=True) if review_author else "Anonymous",
                "Date": review_date.get_text(strip=True) if review_date else "Unknown Date",
                "Rating": review_rating.get_text(strip=True) if review_rating else "No Rating",
                "Review": review_text.get_text(strip=True) if review_text else "No Review",
            })

        return {"Product": product_title, "Rating": rating, "Reviews": review_data}

    except Exception as e:
        return {"error": str(e)}

# ========================= FLASK ROUTES ========================= #
@app.route("/")
def home():
    return jsonify({"message": "Amazon Review Scraper & AI Review Generator"})

@app.route("/generate-review", methods=["POST"])
def api_generate_review():
    """API to generate an AI-based review."""
    data = request.json
    prompt = data.get("prompt", "")

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    generated_review = generate_review(prompt)
    store_review("AI Generated Product", generated_review)
    return jsonify({"review": generated_review})

@app.route("/fetch-reviews/<product_name>", methods=["GET"])
def api_fetch_reviews(product_name):
    """API to fetch reviews from the database."""
    reviews = fetch_reviews(product_name)

    if not reviews:
        return jsonify({"error": "No reviews found"}), 404

    return jsonify([{
        "Product": review[1],
        "Overall Rating": review[2],
        "Title": review[3],
        "Author": review[4],
        "Date": review[5],
        "Rating": review[6],
        "Review": review[7]
    } for review in reviews])

@app.route("/scrape-amazon", methods=["POST"])
def api_scrape_amazon():
    """API to scrape Amazon reviews."""
    data = request.json
    url = data.get("url", "")

    if not url:
        return jsonify({"error": "Amazon URL is required"}), 400

    result = get_amazon_reviews(url)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)

@app.route("/generate-gemini-overview", methods=["POST"])
def api_generate_gemini_overview():
    """API to generate an overview using Gemini AI."""
    data = request.json
    reviews = data.get("reviews", [])

    if not reviews:
        return jsonify({"error": "Reviews are required"}), 400

    overview = generate_summary(reviews)
    return jsonify({"overview": overview})

# ========================= RUN APP ========================= #
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)


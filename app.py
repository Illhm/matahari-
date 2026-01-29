from flask import Flask, render_template, request
import logging
from run import MidtransAutomator
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    snap_token = request.form.get('snap_token')
    card_list_text = request.form.get('card_list')

    if not snap_token or not card_list_text:
        return "Missing SNAP_TOKEN or Card List", 400

    cards = []
    lines = card_list_text.splitlines()
    for line in lines:
        parts = line.strip().split('|')
        if len(parts) >= 4:
             cards.append({
                "card_number": parts[0].strip(),
                "card_exp_month": parts[1].strip(),
                "card_exp_year": parts[2].strip(),
                "card_cvv": parts[3].strip()
            })

    if not cards:
        return "No valid cards found in input. Format should be: number|mm|yy|cvv", 400

    automator = MidtransAutomator()
    results = []

    for card in cards:
        masked_card = f"{card['card_number'][:4]}****{card['card_number'][-4:]}"
        logger.info(f"Processing card: {masked_card}")

        try:
            # We call the process_payment method.
            result_data = automator.process_payment(snap_token, card)
            results.append({
                "card_number": masked_card,
                "status": result_data.get("status", "unknown"),
                "response": result_data.get("response", {})
            })

            # Stop if success, similar to original script behavior
            if result_data.get("status") in ["success", "capture", "completed_with_redirect"]:
                break

        except Exception as e:
            logger.error(f"Error processing card {masked_card}: {e}")
            results.append({
                "card_number": masked_card,
                "status": "error",
                "response": {"error": str(e)}
            })

    return render_template('result.html', results=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

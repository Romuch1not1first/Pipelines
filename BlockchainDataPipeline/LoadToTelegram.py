from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import requests
import logging
import os
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FastAPI_Telegram")

# FastAPI app
app = FastAPI()

# Data model for validation
class TokenData(BaseModel):
    token_pair: Optional[str]
    initial_liquidity: Optional[str]
    contract_address: Optional[str]
    dextools_url: Optional[str]
    token_data: Optional[Dict[str, Any]] = None
    liquidity_data: Optional[Dict[str, Any]] = None
    holders: Optional[int] = None
    burned_tokens: Optional[float] = None
    top_holders: Optional[List[Any]] = None
    tax_info: Optional[Dict[str, Any]] = None
    liquidity_percentage: Optional[float] = None
    airdrops: Optional[List[Any]] = None


def format_liquidity_data(ld: dict) -> str:
    """Return a human-readable string for liquidity data."""
    if not ld:
        return "No liquidity data"
    return (
        f"Base Token: {ld.get('base_token', 'N/A')}\n"
        f"Liquidity Base: {ld.get('liquidity_base', 'N/A')}\n"
        f"Liquidity Token: {ld.get('liquidity_token', 'N/A')}\n"
        f"Market Cap Base: {ld.get('market_cap_base', 'N/A')}"
    )

def format_tax_info(tax: dict) -> str:
    """Return a human-readable string for tax info."""
    if not tax:
        return "No tax info"
    return (
        f"Buy Tax: {tax.get('buy_tax', 'N/A')}%\n"
        f"Sell Tax: {tax.get('sell_tax', 'N/A')}%\n"
        f"Total Tax: {tax.get('total_tax', 'N/A')}%"
    )

def format_top_holders(top_holders: list) -> str:
    """Return a human-readable string for top holders."""
    if not top_holders:
        return "No top holders"
    # If top_holders is just a list of addresses or a list of dicts
    return "\n".join(str(holder) for holder in top_holders)

def format_airdrops(airdrops: list) -> str:
    """Return a user-friendly string for airdrops."""
    if not airdrops:
        return "0"  # show zero instead of empty
    # If you need to list them, e.g. 'user1, user2'
    return ", ".join(str(a) for a in airdrops)

def format_liquidity_percentage(value: float) -> str:
    """Format the liquidity percentage to avoid scientific notation."""
    if value is None:
        return "N/A"
    # For instance, show up to 8 decimal places or fewer:
    return f"{value:.8f}%"

# Function to send message to Telegram
def send_message_to_telegram(data: dict):
    """
    data is a dict produced by data.dict() in the FastAPI route.
    It should match the fields of TokenData.
    """
    try:
        # 1. Format each piece
        liquidity_data_str = format_liquidity_data(data.get("liquidity_data") or {})
        tax_info_str = format_tax_info(data.get("tax_info") or {})
        top_holders_str = format_top_holders(data.get("top_holders") or [])
        airdrops_str = format_airdrops(data.get("airdrops") or [])

        # 2. Format liquidity_percentage
        lp_value = data.get("liquidity_percentage", None)
        liquidity_percentage_str = format_liquidity_percentage(lp_value)

        # 3. Build final message
        holders = data.get("holders", "N/A")
        burned_tokens = data.get("burned_tokens", "N/A")

        message_content = (
            f"🚀 *Token Information:*\n\n"
            f"🔹 *Liquidity Data:*\n{liquidity_data_str}\n\n"
            f"🔹 *Holders:* {holders}\n"
            f"🔹 *Burned Tokens:* {burned_tokens}\n"
            f"🔹 *Top Holders:*\n{top_holders_str}\n\n"
            f"🔹 *Tax Information:*\n{tax_info_str}\n\n"
            f"🔹 Liquidity Percentage: {liquidity_percentage_str}\n"
            f"🔹 Airdrops: {airdrops_str}\n"
        )

        # 4. Send via Telegram Bot API
        url = f"https://api.telegram.org/bot{os.getenv('BOT_TG_TOKEN')}/sendMessage"
        payload = {
            "chat_id": os.getenv('CHAT_BOT_ID'),
            "text": message_content,
            "parse_mode": "Markdown"
        }

        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Message sent successfully to Telegram.")
        else:
            logger.error(f"Failed to send message: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.json())

    except Exception as e:
        logger.error(f"Error sending data to Telegram: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message to Telegram")

# FastAPI route
@app.post("/send_to_telegram")
async def send_to_telegram(data: TokenData):
    logger.info("Received data to send to Telegram.")
    try:
        # Convert TokenData (Pydantic model) to a dict for easy handling
        dict_data = data.dict()
        send_message_to_telegram(dict_data)
        return {"status": "success", "message": "Data sent to Telegram successfully"}
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

import streamlit as st
import requests
import os
import json
import asyncio
import re
import sys
import logging
sys.path.append('.')


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


import importlib.util
spec = importlib.util.spec_from_file_location("mcp_server_module", "server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


st.set_page_config(
    page_title="PolyMCP - Smart Assistant",
    page_icon="🤖",
    layout="centered"
)






def detect_math_question(text):
    math_keywords = ['ضرب', 'تقسیم', 'multiply', 'divide', '×', '÷', '*', '/', 'چند در', 'تقسیم بر']
    text_lower = text.lower()
    

    for keyword in math_keywords:
        if keyword.lower() in text_lower:
            return True
    

    if re.search(r'\d+\s*[×*÷/]\s*\d+', text):
        return True
    
    return False

def detect_price_question(text):
    price_keywords = ['قیمت', 'price', 'ارز', 'crypto', 'bitcoin', 'btc', 'سهام', 'stock', '$', 'dollar']
    text_lower = text.lower()
    
    for keyword in price_keywords:
        if keyword.lower() in text_lower:
            return True
    
    return False

def extract_math_operation(text):
    """Extract numbers and operation from text"""
    # Persian patterns
    persian_mul = re.search(r'ضرب\s*(\d+(?:\.\d+)?)\s*(?:در|و|,|\s)\s*(\d+(?:\.\d+)?)', text)
    if persian_mul:
        return float(persian_mul.group(1)), float(persian_mul.group(2)), 'mul'
    
    persian_div = re.search(r'تقسیم\s*(\d+(?:\.\d+)?)\s*(?:بر|روی|,|\s)\s*(\d+(?:\.\d+)?)', text)
    if persian_div:
        return float(persian_div.group(1)), float(persian_div.group(2)), 'div'
    
    # English/Symbol patterns
    mul_pattern = re.search(r'(\d+(?:\.\d+)?)\s*[×*]\s*(\d+(?:\.\d+)?)', text)
    if mul_pattern:
        return float(mul_pattern.group(1)), float(mul_pattern.group(2)), 'mul'
    
    div_pattern = re.search(r'(\d+(?:\.\d+)?)\s*[÷/]\s*(\d+(?:\.\d+)?)', text)
    if div_pattern:
        return float(div_pattern.group(1)), float(div_pattern.group(2)), 'div'
    
    return None

def extract_ticker(text):
    """Extract ticker symbol from text"""
    # Common crypto patterns
    crypto_patterns = {
        'bitcoin': 'X:BTCUSD',
        'btc': 'X:BTCUSD', 
        'بیت کوین': 'X:BTCUSD',
        'ethereum': 'X:ETHUSD',
        'eth': 'X:ETHUSD'
    }
    
    text_lower = text.lower()
    for key, ticker in crypto_patterns.items():
        if key in text_lower:
            return ticker
    
    # Stock patterns (look for uppercase letters)
    stock_match = re.search(r'([A-Z]{2,5})', text)
    if stock_match:
        return stock_match.group(1)
    
    return None





# Chat interface
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input():
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Process the question intelligently
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                # Check if it's a math question
                if detect_math_question(prompt):
                    st.info("🧮 Detected: Math Question")
                    
                    math_data = extract_math_operation(prompt)
                    if math_data:
                        a, b, operation = math_data
                        logger.info(f"Math question: {operation} {a} and {b}")
                        
                        result = asyncio.run(mod.math_op("math_op", {
                            "operation": operation, 
                            "a": a, 
                            "b": b
                        }))
                        
                        if operation == 'mul':
                            response = f"✅ **{a} × {b} = {result['result']}**"
                        else:
                            response = f"✅ **{a} ÷ {b} = {result['result']}**"
                            
                        st.success(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    else:
                        error_msg = "❌ Sorry, I couldn't understand the math operation. Please try patterns like '5 × 3' or 'ضرب 10 در 2'"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Check if it's a price question
                elif detect_price_question(prompt):
                    st.info("📈 Detected: Price Question")
                    
                    ticker = extract_ticker(prompt)
                    if ticker:
                        logger.info(f"Price question for: {ticker}")
                        
                        result = mod.get_price(ticker)
                        price_text = result.text if hasattr(result, 'text') else str(result)
                        
                        # Try to extract clean price from JSON
                        try:
                            data = json.loads(price_text)
                            if 'results' in data and data['results']:
                                close_price = data['results'][0].get('c', 'N/A')
                                response = f"💰 **{ticker} Price: ${close_price}**"
                            else:
                                response = f"💰 **{ticker}**: {price_text}"
                        except:
                            response = f"💰 **{ticker}**: {price_text}"
                        
                        st.success(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    else:
                        error_msg = "❌ Sorry, I couldn't identify the ticker symbol. Please try 'BTC', 'AAPL', or 'Bitcoin price'"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # If neither math nor price, use Liara AI
                else:
                    st.info("🤖 Using AI Chat")
                    
                    LIARA_API_KEY = os.getenv("LIARA_API_KEY")
                    LIARA_BASE_URL = os.getenv("LIARA_BASE_URL")
                    LIARA_MODEL = os.getenv("LIARA_MODEL", "openai/gpt-4o-mini")
                    
                    if LIARA_API_KEY and LIARA_BASE_URL:
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {LIARA_API_KEY}"
                        }
                        
                        payload = {
                            "model": LIARA_MODEL,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 512
                        }
                        
                        response = requests.post(
                            f"{LIARA_BASE_URL}/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=20
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            ai_response = data["choices"][0]["message"]["content"]
                            st.markdown(ai_response)
                            st.session_state.messages.append({"role": "assistant", "content": ai_response})
                        else:
                            error_msg = f"❌ AI Error: {response.status_code}"
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    else:
                        error_msg = "❌ AI service not configured"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                        
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


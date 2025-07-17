import os
import base64
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_metadata_from_image(file_bytes:bytes)->dict:
    try:
        base64_image = base64.b64encode(file_bytes).decode("utf-8")

        response = client.chat.completions.create(
            model ="gpt-4o",
            messages =[
                {"role":"system" , "content":"you are an expert in analyzing handicraft images. Extract important metadata as structured JSON.Always return valid JSON format."},
                {
                    "role":"user",
                    "content":[
                        {
                            "type":"text",
                            "text":"Extract metadata from this handicraft image. Return ONLY valid JSON with keys:color,material,type,style, estimated_size,handcrafted.No additional text or formatting."
                        },
                        {
                            "type":"image_url",
                            "image_url":{
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens = 500,
            temperature =0.2
        )

        content = response.choices[0].message.content.strip()
        
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as json_error:
            return{
                "error":f"JSON parsing failed:{str(json_error)}",
                "raw_content" : content
            }
    
    except Exception as e:
        return {"error": f"API call failed:{str(e)}"}
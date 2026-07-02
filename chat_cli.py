import requests
import json

URL = "http://localhost:8000/chat"
messages = []

print("Welcome to the SHL Assessment Recommender Chat!")
print("Type 'quit' or 'exit' to stop.\n" + "-" * 50)

while True:
    user_input = input("\nYou: ")
    if user_input.lower() in ['quit', 'exit']:
        break
    
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = requests.post(URL, json={"messages": messages})
        if response.status_code == 200:
            data = response.json()
            reply = data.get("reply", "")
            print(f"\nAssistant: {reply}")
            
            # The API expects us to send back its own responses for conversational history
            messages.append({"role": "assistant", "content": reply})
            
            recommendations = data.get("recommendations", [])
            if recommendations:
                print("\nRecommendations:")
                for rec in recommendations:
                    print(f"- {rec['name']} ({rec['test_type']}): {rec['url']}")
                    
            if data.get("end_of_conversation"):
                print("\n[Conversation Ended]")
                break
        else:
            print(f"\nError: {response.status_code} - {response.text}")
            # Remove the last user message so they can try again
            messages.pop()
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to the server. Is it running on port 8000?")
        messages.pop()

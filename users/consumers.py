from channels.generic.websocket import AsyncWebsocketConsumer
import json

class AnalyticsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        
    async def receive(self, text_data):
        # Handle real-time data updates
        data = json.loads(text_data)
        
        # Broadcast updates to all connected clients
        await self.send(text_data=json.dumps({
            'type': 'analytics_update',
            'data': data
        })) 
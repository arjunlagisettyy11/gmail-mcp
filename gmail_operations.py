import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GmailClient:
    def __init__(self, service, account_name: str = "default"):
        self.service = service
        self.account_name = account_name
    
    def list_messages(self, query='', max_results=10):
        """List messages matching query"""
        try:
            result = self.service.users().messages().list(
                userId='me', 
                q=query, 
                maxResults=max_results
            ).execute()
            
            messages = result.get('messages', [])
            return messages
        except Exception as e:
            print(f'Error listing messages: {e}')
            return []
    
    def get_message(self, message_id):
        """Get a specific message by ID"""
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            return message
        except Exception as e:
            print(f'Error getting message: {e}')
            return None
    
    def get_message_body(self, message):
        """Extract body from message"""
        if not message or 'payload' not in message:
            return ""
            
        payload = message['payload']
        body = ""
        
        def extract_text_from_payload(payload):
            body_text = ""
            
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                        data = part['body']['data']
                        body_text = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
                    # Handle nested parts
                    elif 'parts' in part:
                        body_text = extract_text_from_payload(part)
                        if body_text:
                            break
            else:
                if payload['mimeType'] == 'text/plain' and 'data' in payload.get('body', {}):
                    data = payload['body']['data']
                    body_text = base64.urlsafe_b64decode(data).decode('utf-8')
            
            return body_text
        
        return extract_text_from_payload(payload)
    
    def get_message_headers(self, message):
        """Extract headers from message"""
        if not message or 'payload' not in message:
            return {}
            
        headers = {}
        for header in message['payload'].get('headers', []):
            headers[header['name']] = header['value']
        return headers
    
    def send_message(self, to, subject, body, from_email=None):
        """Send an email message"""
        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            if from_email:
                message['from'] = from_email
            
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode()
            
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            print(f'Message sent. Message ID: {send_message["id"]}')
            return send_message
            
        except Exception as e:
            print(f'Error sending message: {e}')
            return None
    
    def send_message_with_attachment(self, to, subject, body, file_path):
        """Send email with attachment"""
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            
            # Add body
            message.attach(MIMEText(body, 'plain'))
            
            # Add attachment
            if os.path.exists(file_path):
                with open(file_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(file_path)}'
                )
                message.attach(part)
            else:
                print(f"Warning: Attachment file {file_path} not found")
                return None
            
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode()
            
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            print(f'Message with attachment sent. Message ID: {send_message["id"]}')
            return send_message
            
        except Exception as e:
            print(f'Error sending message with attachment: {e}')
            return None
    
    def mark_as_read(self, message_id):
        """Mark message as read"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            print(f'Message {message_id} marked as read')
            return True
        except Exception as e:
            print(f'Error marking message as read: {e}')
            return False
    
    def delete_message(self, message_id):
        """Delete a message"""
        try:
            self.service.users().messages().delete(
                userId='me',
                id=message_id
            ).execute()
            print(f'Message {message_id} deleted')
            return True
        except Exception as e:
            print(f'Error deleting message: {e}')
            return False
    
    def search_messages(self, sender=None, subject=None, after_date=None, has_attachment=False, is_unread=False):
        """Search messages with specific criteria"""
        query_parts = []
        
        if sender:
            query_parts.append(f'from:{sender}')
        if subject:
            query_parts.append(f'subject:"{subject}"')
        if after_date:
            query_parts.append(f'after:{after_date}')
        if has_attachment:
            query_parts.append('has:attachment')
        if is_unread:
            query_parts.append('is:unread')
        
        query = ' '.join(query_parts)
        print(f"Search query: {query}")
        return self.list_messages(query)

import os
import datetime
import discord

async def create_html_transcript(channel: discord.TextChannel, form_data: dict = None):
    messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Ticket Transcript - {channel.name}</title>
        <style>
            body {{
                background-color: #2f3136;
                color: #dcddde;
                font-family: "Whitney", "Helvetica Neue", Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 20px;
            }}
            .message {{
                display: flex;
                margin-bottom: 10px;
                align-items: flex-start;
            }}
            .avatar {{
                width: 40px;
                height: 40px;
                border-radius: 50%;
                margin-right: 10px;
            }}
            .content {{
                background-color: #36393f;
                padding: 10px 15px;
                border-radius: 10px;
                width: fit-content;
                max-width: 80%;
            }}
            .username {{
                color: #00aff4;
                font-weight: bold;
            }}
            .timestamp {{
                color: #72767d;
                font-size: 12px;
                margin-left: 6px;
            }}
            .embed {{
                background-color: #2b2d31;
                border-left: 4px solid #5865f2;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .embed-title {{
                font-weight: bold;
                font-size: 16px;
                margin-bottom: 8px;
            }}
            .embed-field {{
                margin-bottom: 10px;
            }}
            .embed-field-name {{
                font-weight: bold;
                color: #ffffff;
                display: block;
            }}
            .embed-field-value {{
                background-color: #1e1f22;
                padding: 8px;
                border-radius: 4px;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <h2>💬 Transcript: {channel.name}</h2>
        <p>Erstellt am {datetime.datetime.utcnow().strftime('%d.%m.%Y, %H:%M UTC')}</p>
    """

    # Formular-Daten oben einfügen
    if form_data:
        html_content += '<div class="embed">'
        html_content += '<div class="embed-title">📋 Ticket-Formular</div>'
        for question, answer in form_data.items():
            html_content += f'''
                <div class="embed-field">
                    <span class="embed-field-name">{question}</span>
                    <div class="embed-field-value">{answer}</div>
                </div>
            '''
        html_content += '</div>'

    # Nachrichtenverlauf
    for msg in messages:
        avatar_url = msg.author.display_avatar.url if msg.author.display_avatar else ""
        timestamp = msg.created_at.strftime("%b %d, %Y %H:%M")
        content = discord.utils.escape_markdown(msg.content)
        html_content += f"""
        <div class="message">
            <img class="avatar" src="{avatar_url}" alt="avatar">
            <div>
                <div>
                    <span class="username">{msg.author.display_name}</span>
                    <span class="timestamp">{timestamp}</span>
                </div>
                <div class="content">{content}</div>
            </div>
        </div>
        """

    html_content += "</body></html>"

    # Datei speichern
    os.makedirs("transcripts", exist_ok=True)
    file_path = f"transcripts/{channel.name}_transcript.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return file_path

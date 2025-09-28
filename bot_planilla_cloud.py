# bot_planilla_cloud.py - Bot Completo para la Nube
import os
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
from types import SimpleNamespace

# --- CONFIGURACIÓN LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN CLOUD ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8476499368:AAHeJAekWnKssJmVOD3wqq_f_jhVxsUcm2o')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyDj-6_v_nk6HsCC-e7AtXnwWgL54BSUUtQ')

# --- CONFIGURACIÓN DE IA ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash")

# --- CONFIGURACIÓN JSON CLOUD ---
JSON_DATA_FILE = 'registros_planilla.json'
JSON_BACKUP_FILE = 'registros_backup.json'

# --- CONFIGURACIÓN DE CAMPOS ---
FIELD_CONFIG = {
    'fecha': {
        'prompt': '📅 **Fecha** (DD/MM/YYYY o "hoy"):',
        'default': lambda: datetime.now().strftime('%d/%m/%Y'),
        'quick_options': ['hoy']
    },
    'hora': {
        'prompt': '⏰ **Hora(s) de visita** - Puedes seleccionar varias:',
        'default': lambda: datetime.now().strftime('%H:%M'),
        'quick_options': ['8:00', '10:00', '12:00', '14:00', '16:00', '18:00'],
        'multiple': True
    },
    'visita': {
        'prompt': '👀 **Observaciones de visita**:',
        'default': lambda: 'Normal',
        'quick_options': ['Normal', 'Sin novedad']
    },
    'bomba1': {
        'prompt': '🔧 **Bomba 1**:',
        'default': lambda: 'Funcionando',
        'quick_options': ['Funcionando', 'Parada', 'Mantenimiento']
    },
    'bomba2': {
        'prompt': '🔧 **Bomba 2**:',
        'default': lambda: 'Funcionando',
        'quick_options': ['Funcionando', 'Parada', 'Mantenimiento']
    },
    'caudal': {
        'prompt': '💧 **Caudal**:',
        'default': lambda: 'Normal',
        'quick_options': ['Normal']
    },
    'nivel_pozo': {
        'prompt': '📊 **Nivel del Pozo**:',
        'default': lambda: 'Medio',
        'quick_options': ['Alto', 'Medio', 'Bajo']
    },
    'solidos': {
        'prompt': '🧪 **Sólidos (CC)**:',
        'default': lambda: '0'
    },
    'oxigeno_disuelto': {
        'prompt': '🫧 **Oxígeno Disuelto (mg/l)**:',
        'default': lambda: '0'
    },
    'cloro': {
        'prompt': '🟢 **Cloro (mg/l)**:',
        'default': lambda: '0'
    },
    'ph': {
        'prompt': '⚖️ **pH**:',
        'default': lambda: '7.0'
    },
    'medidor_salida': {
        'prompt': '📏 **Medidor de salida**:',
        'default': lambda: '0'
    },
    'aseo_alrededores': {
        'prompt': '🧹 **¿Aseo alrededores?**',
        'default': lambda: 'NO',
        'quick_options': ['SI', 'NO']
    },
    'lavado_canastilla': {
        'prompt': '🧺 **¿Lavado canastilla?**',
        'default': lambda: 'NO',
        'quick_options': ['SI', 'NO']
    },
    'desalojo_lodos': {
        'prompt': '🚛 **¿Desalojo de lodos?**',
        'default': lambda: 'NO',
        'quick_options': ['SI', 'NO']
    },
    'limpieza_sedimentador': {
        'prompt': '🧽 **¿Limpieza sedimentador?**',
        'default': lambda: 'NO',
        'quick_options': ['SI', 'NO']
    }
}

FIELD_ORDER = list(FIELD_CONFIG.keys())

# --- GESTOR DE DATOS JSON CLOUD ---
class CloudDataManager:
    @staticmethod
    def init_json_files():
        for json_file in [JSON_DATA_FILE, JSON_BACKUP_FILE]:
            if not os.path.exists(json_file):
                initial_data = {
                    'metadata': {
                        'created': datetime.now().isoformat(),
                        'version': '1.0',
                        'total_records': 0
                    },
                    'records': []
                }
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Archivo JSON creado: {json_file}")
    
    @staticmethod
    def save_record(record_data: dict) -> bool:
        try:
            new_record = {
                'id': datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3],
                'timestamp': datetime.now().isoformat(),
                'data': record_data
            }
            
            with open(JSON_DATA_FILE, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            json_data['records'].append(new_record)
            json_data['metadata']['total_records'] = len(json_data['records'])
            json_data['metadata']['last_updated'] = datetime.now().isoformat()
            
            with open(JSON_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            with open(JSON_BACKUP_FILE, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Registro guardado - Total: {json_data['metadata']['total_records']}")
            return True
            
        except Exception as e:
            logger.error(f"Error en save_record: {e}")
            return False
    
    @staticmethod
    def get_stats() -> dict:
        try:
            with open(JSON_DATA_FILE, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                
            file_size = 0
            if os.path.exists(JSON_DATA_FILE):
                file_size = round(os.path.getsize(JSON_DATA_FILE) / 1024, 2)
            
            return {
                'total_records': json_data['metadata'].get('total_records', 0),
                'last_updated': json_data['metadata'].get('last_updated', 'Nunca'),
                'file_size_kb': file_size
            }
        except:
            return {'total_records': 0, 'last_updated': 'Nunca', 'file_size_kb': 0}

# --- VALIDADOR ---
class FastValidator:
    @staticmethod
    def normalize_input(value: str, field_name: str) -> str:
        value = value.strip()
        
        if field_name == 'fecha':
            if value.lower() in ['hoy', 'today']:
                return datetime.now().strftime('%d/%m/%Y')
            if '/' in value:
                parts = value.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2:
                        year = '20' + year
                    return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        
        elif field_name == 'hora':
            if value.lower() == 'ahora':
                return datetime.now().strftime('%H:%M')
            if ':' not in value and value.isdigit():
                hour = int(value)
                if 0 <= hour <= 23:
                    return f"{hour:02d}:00"
        
        elif field_name in ['aseo_alrededores', 'lavado_canastilla', 'desalojo_lodos', 'limpieza_sedimentador']:
            if value.lower() in ['s', 'si', 'yes', '1']:
                return 'SI'
            elif value.lower() in ['n', 'no', '0', '']:
                return 'NO'
        
        elif field_name == 'nivel_pozo':
            value_lower = value.lower()
            if 'alt' in value_lower:
                return 'Alto'
            elif 'med' in value_lower:
                return 'Medio'
            elif 'baj' in value_lower:
                return 'Bajo'
        
        return value

# --- TECLADOS ---
def create_quick_keyboard(field_name: str) -> Optional[InlineKeyboardMarkup]:
    config = FIELD_CONFIG.get(field_name)
    if not config or 'quick_options' not in config:
        return None
    
    keyboard = []
    options = config['quick_options']
    
    if field_name == 'hora':
        for i in range(0, len(options), 3):
            row = [
                InlineKeyboardButton(opt, callback_data=f"{field_name}:add:{opt}")
                for opt in options[i:i+3]
            ]
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("✍️ Escribir hora personalizada", callback_data=f"{field_name}:custom")
        ])
        
        keyboard.append([
            InlineKeyboardButton("✅ Finalizar selección", callback_data=f"{field_name}:finish")
        ])
    else:
        for i in range(0, len(options), 3):
            row = [
                InlineKeyboardButton(opt, callback_data=f"{field_name}:{opt}")
                for opt in options[i:i+3]
            ]
            keyboard.append(row)
        
        if 'default' in config:
            default_val = config['default']()
            keyboard.append([
                InlineKeyboardButton(f"⏭️ Default ({default_val})", callback_data=f"{field_name}:DEFAULT")
            ])
    
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
data_manager = CloudDataManager()
validator = FastValidator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['current_field_index'] = 0
    context.user_data['record_data'] = {}
    context.user_data['start_time'] = datetime.now()
    
    stats = data_manager.get_stats()
    
    await update.message.reply_text(
        "🌱 **Bot de Planilla Cloud**\n\n"
        f"📊 Registros totales: {stats['total_records']}\n"
        f"💾 Tamaño datos: {stats['file_size_kb']} KB\n\n"
        "📋 16 campos básicos a completar\n"
        "⚡ Usa botones para rapidez\n"
        "🕐 Múltiples horarios de visita\n\n"
        "Empezamos:"
    )
    
    await ask_current_field(update, context)

async def ask_current_field(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    field_index = context.user_data.get('current_field_index', 0)
    
    if field_index >= len(FIELD_ORDER):
        await finalize_record(update, context, from_callback=from_callback)
        return
    
    field_name = FIELD_ORDER[field_index]
    config = FIELD_CONFIG[field_name]
    
    progress = f"({field_index + 1}/{len(FIELD_ORDER)})"
    prompt = f"{progress} {config['prompt']}"
    
    keyboard = create_quick_keyboard(field_name)
    
    if from_callback:
        if keyboard:
            await update.callback_query.message.reply_text(prompt, reply_markup=keyboard)
        else:
            await update.callback_query.message.reply_text(prompt)
    else:
        if keyboard:
            await update.message.reply_text(prompt, reply_markup=keyboard)
        else:
            await update.message.reply_text(prompt)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        callback_parts = query.data.split(':', 2)
        field_name = callback_parts[0]
        action = callback_parts[1] if len(callback_parts) > 1 else None
        value = callback_parts[2] if len(callback_parts) > 2 else action
        
        current_index = context.user_data.get('current_field_index', 0)
        expected_field = FIELD_ORDER[current_index]
        
        if field_name != expected_field:
            await query.edit_message_text(f"❌ Campo incorrecto")
            return
        
        if field_name == 'hora':
            await handle_hora_callback(query, context, action, value)
            return
        
        if value == 'DEFAULT':
            config = FIELD_CONFIG[field_name]
            value = config['default']()
        
        await process_field_input(value, field_name, update, context, from_callback=True)
        
    except Exception as e:
        logger.error(f"Error en callback: {e}")
        await query.edit_message_text("❌ Error. Usa /start")

async def handle_hora_callback(query, context: ContextTypes.DEFAULT_TYPE, action: str, value: str):
    if 'selected_hours' not in context.user_data:
        context.user_data['selected_hours'] = []
    
    selected_hours = context.user_data['selected_hours']
    
    if action == 'add':
        if value not in selected_hours:
            selected_hours.append(value)
            context.user_data['selected_hours'] = selected_hours
        
        hours_text = ", ".join(selected_hours) if selected_hours else "Ninguna"
        await query.edit_message_text(
            f"⏰ **Horas seleccionadas**: {hours_text}\n\n"
            "Selecciona más horas o finaliza:",
            reply_markup=create_quick_keyboard('hora')
        )
    
    elif action == 'custom':
        context.user_data['awaiting_custom_hour'] = True
        await query.edit_message_text(
            f"⏰ **Horas actuales**: {', '.join(selected_hours) if selected_hours else 'Ninguna'}\n\n"
            "✍️ **Escribe la hora personalizada** (ej: 7:30, 15:45):"
        )
    
    elif action == 'finish':
        if not selected_hours:
            current_time = datetime.now().strftime('%H:%M')
            selected_hours = [current_time]
            context.user_data['selected_hours'] = selected_hours
        
        hours_string = ", ".join(selected_hours)
        context.user_data.pop('selected_hours', None)
        
        mock_update = SimpleNamespace()
        mock_update.callback_query = query
        mock_update.message = query.message
        
        await process_field_input(hours_string, 'hora', mock_update, context, from_callback=True)

async def process_field_input(input_value: str, field_name: str, update: Update, 
                            context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    normalized_value = validator.normalize_input(input_value, field_name)
    context.user_data['record_data'][field_name] = normalized_value
    
    confirmation = f"✅ **{field_name.replace('_', ' ').title()}**: {normalized_value}"
    
    if from_callback:
        await update.callback_query.edit_message_text(confirmation)
    else:
        await update.message.reply_text(confirmation)
    
    context.user_data['current_field_index'] += 1
    await asyncio.sleep(0.3)
    await ask_current_field(update, context, from_callback=from_callback)

async def finalize_record(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    record_data = context.user_data.get('record_data', {})
    start_time = context.user_data.get('start_time')
    
    if start_time:
        elapsed = datetime.now() - start_time
        time_str = f" en {elapsed.seconds}s"
    else:
        time_str = ""
    
    if from_callback:
        await update.callback_query.message.reply_text(f"☁️ Guardando en la nube{time_str}...")
    else:
        await update.message.reply_text(f"☁️ Guardando en la nube{time_str}...")
    
    success = data_manager.save_record(record_data)
    
    if success:
        stats = data_manager.get_stats()
        final_message = (
            "✅ **¡Registro guardado en la nube!**\n\n"
            f"⏱️ Completado{time_str}\n"
            f"📊 Total registros: {stats['total_records']}\n"
            f"💾 Datos: {stats['file_size_kb']} KB\n\n"
            "🔄 /start - Nuevo registro\n"
            "📊 /stats - Ver estadísticas\n"
            "⬇️ /descargar - Obtener JSON"
        )
        context.user_data.clear()
    else:
        final_message = (
            "⚠️ **Error guardando en cloud**\n\n"
            "🔄 /start para intentar de nuevo"
        )
    
    if from_callback:
        await update.callback_query.message.reply_text(final_message)
    else:
        await update.message.reply_text(final_message)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_custom_hour'):
        custom_hour = update.message.text.strip()
        normalized_hour = validator.normalize_input(custom_hour, 'hora')
        
        if 'selected_hours' not in context.user_data:
            context.user_data['selected_hours'] = []
        
        context.user_data['selected_hours'].append(normalized_hour)
        context.user_data.pop('awaiting_custom_hour', None)
        
        selected_hours = context.user_data['selected_hours']
        hours_text = ", ".join(selected_hours)
        
        await update.message.reply_text(
            f"✅ **Hora añadida**: {normalized_hour}\n"
            f"⏰ **Horas totales**: {hours_text}\n\n"
            "Selecciona más horas o finaliza:",
            reply_markup=create_quick_keyboard('hora')
        )
        return
    
    if 'current_field_index' not in context.user_data:
        await update.message.reply_text("Usa /start para comenzar")
        return
    
    field_index = context.user_data['current_field_index']
    if field_index >= len(FIELD_ORDER):
        return
    
    field_name = FIELD_ORDER[field_index]
    input_value = update.message.text
    
    if field_name == 'hora' and 'selected_hours' in context.user_data:
        normalized_hour = validator.normalize_input(input_value, 'hora')
        context.user_data['selected_hours'].append(normalized_hour)
        
        selected_hours = context.user_data['selected_hours']
        hours_text = ", ".join(selected_hours)
        
        await update.message.reply_text(
            f"✅ **Hora añadida**: {normalized_hour}\n"
            f"⏰ **Horas totales**: {hours_text}\n\n"
            "Selecciona más horas o finaliza:",
            reply_markup=create_quick_keyboard('hora')
        )
        return
    
    await process_field_input(input_value, field_name, update, context)

# --- COMANDOS ADICIONALES ---
async def get_cloud_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = data_manager.get_stats()
    
    await update.message.reply_text(
        "📊 **Estadísticas Cloud**\n\n"
        f"🗂️ Total registros: {stats['total_records']}\n"
        f"💾 Tamaño archivo: {stats['file_size_kb']} KB\n"
        f"⏰ Última actualización: {stats['last_updated'][:16] if stats['last_updated'] != 'Nunca' else 'Nunca'}\n"
        f"📍 Servidor: Render.com\n\n"
        "⬇️ /descargar - Obtener datos JSON"
    )

async def download_json(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(JSON_DATA_FILE):
        await update.message.reply_text("📭 No hay datos para descargar")
        return
    
    try:
        with open(JSON_DATA_FILE, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"registros_planilla_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                caption="☁️ **Datos de la nube**\n\nArchivo JSON con todos los registros"
            )
    except Exception as e:
        logger.error(f"Error enviando JSON: {e}")
        await update.message.reply_text("❌ Error enviando archivo")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Registro cancelado. Usa /start")

def main():
    data_manager.init_json_files()
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stats", get_cloud_stats))
    app.add_handler(CommandHandler("descargar", download_json))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Configuración para Render.com
    PORT = int(os.environ.get('PORT', 8443))
    
    logger.info("🌱 Bot Planilla Cloud iniciando...")
    logger.info(f"📊 Puerto: {PORT}")
    
    # Modo webhook para Render.com
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=f"https://bot-planilla-tratamiento-abc123.onrender.com/{TELEGRAM_BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()

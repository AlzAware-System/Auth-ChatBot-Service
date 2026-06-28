"""Scan Service — Business logic for MRI scan analysis."""

import os
import uuid
import numpy as np

from app.utils.error_handler import AppError, ValidationError, AuthError
from app.utils.response import success_response
from app.utils.jwt import decode_token, JWTError

# ==========================================
# === 1. Build model and load weights ===
# ==========================================

# Lazy imports to avoid issues when TensorFlow is not available
try:
    import tensorflow as tf
    from tensorflow.keras.preprocessing import image
    from tensorflow.keras.applications.resnet50 import ResNet50
    from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout
    from tensorflow.keras.models import Model
    import google.generativeai as genai

    MODEL_PATH = '/home/ubuntu/mobile/models/Alzheimer_ResNet50_model.h5'

    def build_alzheimer_model():
        """بناء الهيكل المتطابق تماماً مع الكود اللي انت دربته"""
        base_model = ResNet50(weights=None, include_top=False, input_shape=(224, 224, 3))
        x = base_model.output
        x = GlobalAveragePooling2D(name='global_average_pooling2d_2')(x)
        x = Dense(256, activation='relu', name='dense_4')(x)
        x = Dropout(0.5, name='dropout_2')(x)
        predictions = Dense(4, activation='softmax', name='dense_5')(x)
        model = Model(inputs=base_model.input, outputs=predictions)
        return model

    try:
        cnn_model = build_alzheimer_model()
        cnn_model.load_weights(MODEL_PATH, by_name=True, skip_mismatch=True)
        print("[OK] Alzheimer_ResNet50_model weights loaded successfully into custom architecture.")
    except Exception as e:
        print(f"[ERROR] Could not load CNN weights: {e}")
        cnn_model = None

    # Gemini API
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)

    try:
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    except Exception:
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')

except ImportError:
    cnn_model = None
    gemini_model = None
    image = None

CLASS_NAMES = ['MildDemented', 'ModerateDemented', 'NonDemented', 'VeryMildDemented']

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


# ==========================================
# === Service method ===
# ==========================================

def analyze_mri(token: str, img_file, lang: str = 'ar'):
    if not token:
        raise AuthError('Missing Bearer token')
    try:
        decode_token(token)
    except JWTError as e:
        raise AuthError(str(e))

    if not img_file:
        raise ValidationError('No image file provided. Use form-data with key "image".')

    unique_id = uuid.uuid4().hex
    tmp_path = f"/tmp/mri_{unique_id}.jpg"

    try:
        img_file.save(tmp_path)

        if not cnn_model:
            raise AppError('Alzheimer CNN Model is not initialized on the server.', status_code=500)

        # تجهيز الصورة بنفس طريقة تدريبك
        img = image.load_img(tmp_path, target_size=(224, 224))
        img_array = image.img_to_array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        # التوقع
        pred = cnn_model.predict(img_array)
        class_idx = np.argmax(pred)
        predicted_class = CLASS_NAMES[class_idx]
        confidence = round(float(np.max(pred)) * 100, 2)

        if lang == 'en':
            prompt_text = f"""
            You are an intelligent medical assistant specializing in neurology, specifically Alzheimer's disease.

            An MRI scan of a patient was analyzed by an AI model with the following result:
            - Classification: {predicted_class}
            - Confidence: {confidence}%

            Write a structured medical report ONLY in English, containing the following sections:
            1. **Diagnosis Summary**: What this classification means in simple terms.
            2. **Expected Symptoms**: Common symptoms at this stage.
            3. **Recommended Next Steps**: Medical care advice.
            4. **Safety Notes**: Safety guidelines for the patient.
            5. **Disclaimer**: A warning that this is an initial AI analysis and does not replace a specialist's diagnosis.

            Make the report accurate, professional, and empathetic.
            """
        else:
            prompt_text = f"""
            أنت مساعد طبي ذكي متخصص في أمراض المخ والأعصاب، وتحديداً مرض الزهايمر.

            تم تحليل أشعة رنين مغناطيسي (MRI) للمريض بواسطة نموذج ذكاء اصطناعي وكانت النتيجة:
            - التصنيف: {predicted_class}
            - نسبة الدقة: {confidence}%

            اكتب تقريراً طبياً منظماً باللغة العربية فقط (لا تستخدم أي مصطلحات إنجليزية)، يحتوي على الأقسام التالية:
            1. **ملخص التشخيص**: ماذا يعني هذا التصنيف بطريقة مبسطة.
            2. **الأعراض المتوقعة**: الأعراض الشائعة في هذه المرحلة.
            3. **الخطوات القادمة المقترحة**: نصائح للرعاية الطبية.
            4. **ملاحظات السلامة**: إرشادات أمان للمريض.
            5. **إخلاء مسؤولية**: تنبيه أن هذا تحليل أولي بالذكاء الاصطناعي ولا يغني عن تشخيص الطبيب المختص.

            اجعل التقرير دقيقاً، مهنياً، ومتعاطفاً.
            """

        response = gemini_model.generate_content(prompt_text, safety_settings=safety_settings)
        try:
            report_text = response.text
        except ValueError:
            report_text = "عذراً، تعذر توليد التقرير لأسباب أمنية." if lang == 'ar' else "Sorry, report generation failed due to safety reasons."

        return success_response(
            data={
                "prediction": predicted_class,
                "confidence": confidence,
                "report": report_text
            },
            message="MRI Scan analyzed successfully",
            status_code=200
        )

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

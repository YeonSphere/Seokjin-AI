import tensorflow as tf
import yaml
import whisper
import os
import logging
import logging.config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load logging configuration
with open('./config/logging.yaml', 'r') as file:
    logging_config = yaml.safe_load(file)
logging.config.dictConfig(logging_config)
logger = logging.getLogger('my_app')

try:
    # Check required environment variables
    if not os.getenv('REQUIRED_ENV_VAR'):
        logger.error("Required environment variable 'REQUIRED_ENV_VAR' is not set.")
        raise EnvironmentError("Required environment variable 'REQUIRED_ENV_VAR' is not set.")

    # Load configuration
    with open('./config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)

    # Load model architecture
    try:
        with open('./models/model_architecture.json', 'r') as file:
            model_json = file.read()
    except FileNotFoundError:
        logger.error("Model architecture file not found.")
        raise

    model = tf.keras.models.model_from_json(model_json)

    # Set mixed precision policy
    tf.keras.mixed_precision.set_global_policy('mixed_float16')

    # Compile model with mixed precision
    optimizer = tf.keras.optimizers.Adam(learning_rate=config['optimizer']['learning_rate'])
    model.compile(optimizer=optimizer, loss='sparse_categorical_crossentropy', metrics=['accuracy'])

    # Data augmentation
    from tensorflow.keras.preprocessing.image import ImageDataGenerator

    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=40,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True,
        fill_mode='nearest'
    )

    train_data = train_datagen.flow_from_directory(
        './datasets/train',
        target_size=(224, 224),
        batch_size=32,
        class_mode='sparse'
    )

    val_datagen = ImageDataGenerator(rescale=1./255)
    val_data = val_datagen.flow_from_directory(
        './datasets/validation',
        target_size=(224, 224),
        batch_size=32,
        class_mode='sparse'
    )

    # Model checkpointing
    checkpoint_callback = tf.keras.callbacks.ModelCheckpoint(
        filepath='./models/checkpoints/best_model',
        save_best_only=True,
        monitor='val_loss',
        mode='min'
    )

    # Train model with mixed precision
    model.fit(
        train_data,
        validation_data=val_data,
        epochs=config['training']['epochs'],
        callbacks=[checkpoint_callback]
    )

    # Save model
    model.save('./models/best_model')

    # Whisper integration for speech recognition
    try:
        whisper_model = whisper.load_model("base")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
        raise

    # Process all audio files in the audio directory
    audio_path = './datasets/audio'
    for audio_file in os.listdir(audio_path):
        if audio_file.endswith('.wav'):
            audio_file_path = os.path.join(audio_path, audio_file)
            result = whisper_model.transcribe(audio_file_path)
            logger.info(f"Transcription for {audio_file}: {result['text']}")

except Exception as e:
    logger.error(f"An error occurred: {e}", exc_info=True)

"""
Training Script — Train XGBoost + Random Forest ensemble.

Usage:
    cd ML_Model
    python train.py
    python train.py --data-file data/training_sms.csv
"""

import os
import json
import logging
import argparse
from datetime import datetime

import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import classification_report, f1_score
from scipy.sparse import hstack

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("finsight.train")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def generate_training_data():
    """
    Generate training data using rule-based labeler (weak supervision bootstrap).
    In production, this would be replaced with actual labeled SMS data.
    """
    from pipeline.labeler import rule_based_label
    from pipeline.preprocessor import normalize_text

    # Indian banking SMS samples (representative examples)
    samples = [
        # Financial transactions
        "Rs.2,500.00 debited from A/c XX1234 on 15-01-2025. UPI Ref: 503219876543. Avl bal: Rs.45,678.90 - HDFC Bank",
        "INR 1,200.00 credited to your A/c XX5678 by UPI. Ref: 612345678901. Bal: 23456.78 - SBI",
        "Your A/c XX9012 has been debited with Rs.499.00 towards NETFLIX. UPI Ref No: 412345678901",
        "Rs 3500 sent to Swiggy via UPI from HDFC Bank. Ref: 512345678901",
        "Payment of Rs.8999 received from Amazon Pay. Credited to XX3456",
        "Rs.15,000 transferred via IMPS to Axis Bank A/c. Ref: IMPS20250101234567",
        "ATM withdrawal of Rs.10000 from your A/c XX7890. Available balance: Rs.35,678",
        "Your Credit Card XX4321 has been charged Rs.2,499 at Flipkart",
        "Rs.649 debited from A/c for Google Play subscription. Bal: Rs.12345 - ICICI",
        "INR 799 paid to Spotify via PhonePe. UPI: 712345678901",
        "Salary of Rs.75,000 credited to your A/c XX1111. Bal: Rs.1,23,456 - SBI", 
        "Rs.450.00 debited for Zomato order via Paytm. Ref.789012345678",
        "EMI of Rs.12,500 debited from A/c XX2222 towards Home Loan. HDFC",
        "Rs.199 paid to YouTube Premium. UPI Ref: 912345678901. Bal: Rs.8,765",
        "NEFT of Rs.50,000 credited to A/c XX3333. Ref: NEFT20250127123456",

        # Financial alerts  
        "Alert: Your A/c XX1234 balance is below Rs.1000. Current balance: Rs.567.89",
        "Your account statement for January 2025 is ready. Login to view.",
        "Interest of Rs.1,234.56 credited to your Savings A/c XX5678",
        "Your FD of Rs.1,00,000 is maturing on 15-Feb-2025. Contact your branch.",
        "EMI due reminder: Rs.8,500 for Personal Loan A/c 12345. Due: 05-Feb-2025",
        "Credit limit on Card XX9999 increased to Rs.2,00,000. Enjoy!",
        "Your CIBIL Score is 756. Check detailed report on our app.",
        "Insurance premium of Rs.12,000 due on 20-Feb-2025. Pay to avoid lapse.",

        # OTP
        "123456 is your OTP for UPI transaction of Rs.500 on PhonePe. Valid for 10 min. Do not share.",
        "Your OTP for HDFC Bank login is 789012. Valid for 5 minutes.",
        "456789 is your one-time password for Amazon order #123-456. Don't share this code.",
        "Verification code: 234567. Use this to verify your Paytm account.",
        "OTP for transaction: 890123. Valid for 3 min. Never share your OTP.",
        "Your secure code is 567890 for ICICI Bank transaction.",

        # Promotional
        "Flat 50% OFF on Swiggy! Use code SAVE50. Order now and save big! T&C apply.",
        "Earn 5X reward points on all online shopping with your HDFC Credit Card this weekend!",
        "Amazon Great Indian Festival: Up to 80% off on electronics. Shop now!",
        "Get Rs.200 cashback on your first UPI payment via PhonePe. Offer valid till 31st Jan.",
        "Upgrade to Spotify Premium at just Rs.59/month. Limited time offer!",
        "Your Cred coins are expiring! Redeem 50,000 coins for exclusive rewards.",
        "Myntra End of Reason Sale: Extra 10% off on HDFC Cards. Unsubscribe: STOP",
        "Flipkart Big Saving Days! Up to 75% off on mobiles. Don't miss out!",
        "Get 2% additional cashback on all Paytm UPI payments. Use code PAYTM2.",

        # Personal
        "Hey, are you coming for dinner tonight?",
        "Happy Birthday! Wishing you a great year ahead.",
        "Meeting confirmed for tomorrow at 3 PM in the office.",
        "Don't forget to pick up groceries on your way home.",
        "Your cab is arriving in 2 minutes. Driver: Raj (KA01XX1234)",

        # Spam
        "CONGRATULATIONS! You won Rs.25,00,000 in our lucky draw! Click here to claim: bit.ly/xyz",
        "Your KYC is expiring! Update immediately or your account will be blocked: tinyurl.com/abc",
        "Earn Rs.50,000 daily from home! No investment needed. Call now: 9876543210",
        "Your SBI account will be suspended. Verify your details here: short.link/verify",
    ]

    texts = []
    labels = []
    for sms in samples:
        label, conf = rule_based_label(sms)
        texts.append(sms)
        labels.append(label)

    return texts, labels


def train_model(texts=None, labels=None, save=True):
    """Train the ensemble classifier and save models."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    if texts is None or labels is None:
        logger.info("Generating training data via weak supervision...")
        texts, labels = generate_training_data()

    logger.info("Training on %d samples", len(texts))
    from pipeline.preprocessor import normalize_text, engineer_features

    # Normalize texts
    normalized = [normalize_text(t) for t in texts]

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 3),
        sublinear_tf=True,
        min_df=1,
    )
    tfidf_matrix = vectorizer.fit_transform(normalized)

    # Engineered features
    eng_features = np.array([engineer_features(t) for t in texts])

    # Combine
    X = hstack([tfidf_matrix, eng_features])

    # Label encoding
    le = LabelEncoder()
    y = le.fit_transform(labels)

    logger.info("Classes: %s", list(le.classes_))
    logger.info("Class distribution: %s", dict(zip(le.classes_, np.bincount(y))))

    # Build ensemble
    if XGBClassifier:
        xgb = XGBClassifier(
            n_estimators=600,
            max_depth=7,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric='mlogloss',
            random_state=42,
        )
    else:
        logger.warning("XGBoost not available, using extra RandomForest instead")
        xgb = RandomForestClassifier(n_estimators=600, max_depth=7, random_state=42)

    rf = RandomForestClassifier(
        n_estimators=300,
        min_samples_leaf=2,
        random_state=42,
    )

    # Soft-voting ensemble: 0.55 × XGB + 0.45 × RF
    ensemble = VotingClassifier(
        estimators=[('xgb', xgb), ('rf', rf)],
        voting='soft',
        weights=[0.55, 0.45],
    )

    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(ensemble, X, y, cv=cv, scoring='accuracy')
    f1_scores = cross_val_score(ensemble, X, y, cv=cv, scoring='f1_weighted')

    logger.info("CV Accuracy: %.4f ± %.4f", cv_scores.mean(), cv_scores.std())
    logger.info("CV Weighted F1: %.4f ± %.4f", f1_scores.mean(), f1_scores.std())

    # Train final model on all data
    ensemble.fit(X, y)

    # Classification report
    y_pred = ensemble.predict(X)
    report = classification_report(le.inverse_transform(y), le.inverse_transform(y_pred))
    logger.info("Training Classification Report:\n%s", report)

    if save:
        # Save models
        joblib.dump(vectorizer, os.path.join(MODEL_DIR, "vectorizer.joblib"))
        joblib.dump(ensemble, os.path.join(MODEL_DIR, "classifier.joblib"))
        joblib.dump(le, os.path.join(MODEL_DIR, "label_encoder.joblib"))

        # Save metrics
        metrics = {
            "samples": len(texts),
            "cv_accuracy": round(float(cv_scores.mean()), 4),
            "cv_accuracy_std": round(float(cv_scores.std()), 4),
            "cv_f1_weighted": round(float(f1_scores.mean()), 4),
            "cv_f1_std": round(float(f1_scores.std()), 4),
            "classes": list(le.classes_),
            "class_distribution": {c: int(n) for c, n in zip(le.classes_, np.bincount(y))},
            "training_date": datetime.now().isoformat(),
        }
        with open(os.path.join(MODEL_DIR, "training_metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info("Models saved to %s", MODEL_DIR)

    return ensemble, vectorizer, le, cv_scores


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FinSight SMS classifier")
    parser.add_argument("--data-file", type=str, help="Path to CSV training data")
    args = parser.parse_args()

    if args.data_file:
        import pandas as pd
        df = pd.read_csv(args.data_file)
        texts = df["text"].tolist()
        labels = df["label"].tolist()
        train_model(texts, labels)
    else:
        train_model()

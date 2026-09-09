import argparse
import os
import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

def evaluate(model_path, test_data_path):
    print(f"Evaluating model: {model_path}")
    if not os.path.exists(model_path) or not os.path.exists(test_data_path):
        print("Model or test data not found.")
        return
        
    clf = joblib.load(model_path)
    df = pd.read_csv(test_data_path)
    
    features = ['rolling_mean', 'signal_variance', 'first_derivative', 'deviation_from_baseline']
    X = df[features].fillna(0)
    y_true = (df['condition'] == 'FLAME').astype(int)
    
    y_pred = clf.predict(X)
    y_prob = clf.predict_proba(X)[:, 1] if hasattr(clf, "predict_proba") else y_pred
    
    print("\n--- CONFUSION MATRIX ---")
    print(confusion_matrix(y_true, y_pred))
    
    print("\n--- CLASSIFICATION REPORT ---")
    print(classification_report(y_true, y_pred))
    
    print(f"\nROC-AUC Score: {roc_auc_score(y_true, y_prob):.2f}")
    
    print("\nNOTE: Ensure this test data is from a completely separate session than training data.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to trained model .pkl")
    parser.add_argument("--test_data", required=True, help="Path to test CSV")
    args = parser.parse_args()
    evaluate(args.model, args.test_data)

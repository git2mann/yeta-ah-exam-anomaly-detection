# -*- coding: utf-8 -*-
"""Project Yeta Ah.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1J_dAtGJe9mX9iCDsWdxTvUQMzKx1WAVT

# **Data Generation and Preprocessing**
"""

# %%
# Data Generation and Preprocessing
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
from sklearn.utils.class_weight import compute_class_weight
from sklearn.ensemble import IsolationForest
import joblib


def generate_realistic_cheating_data(n_samples=1000, cheater_ratio=0.15):
    """
    Generates realistic dummy dataset for cheater detection with clear patterns.

    Parameters:
    -----------
    n_samples : int
        Number of students to generate data for
    cheater_ratio : float
        Proportion of students who are cheaters (between 0 and 1)

    Returns:
    --------
    pandas.DataFrame
        DataFrame with features and target variable
    """
    np.random.seed(42)  # for reproducibility

    # Determine number of cheaters
    n_cheaters = int(n_samples * cheater_ratio)
    n_non_cheaters = n_samples - n_cheaters

    # Generate non-cheater data first
    non_cheaters = pd.DataFrame({
        # Base academic performance (underlying ability)
        'ability': np.random.normal(0, 1, n_non_cheaters),
        'cheater': np.zeros(n_non_cheaters, dtype=int)
    })

    # Generate coursework and exam scores based on ability for non-cheaters
    non_cheaters['coursework_raw'] = non_cheaters['ability'] + np.random.normal(0, 0.8, n_non_cheaters)
    non_cheaters['exam_raw'] = non_cheaters['ability'] + np.random.normal(0, 0.8, n_non_cheaters)

    # Generate cheater data
    cheaters = pd.DataFrame({
        # Base academic performance (slightly lower on average)
        'ability': np.random.normal(-0.5, 1, n_cheaters),
        'cheater': np.ones(n_cheaters, dtype=int)
    })

    # Generate coursework scores based on ability for cheaters
    cheaters['coursework_raw'] = cheaters['ability'] + np.random.normal(0, 0.8, n_cheaters)

    # Generate exam scores with CLEAR differences for cheaters:
    # 1. Some cheaters do much better on coursework than exams (copied/plagiarized)
    # 2. Some cheaters do exceptionally well on exams (had advance knowledge)
    # 3. Some cheaters show suspicious pattern consistency

    # Split cheaters into different types
    cheater_types = np.random.choice(['coursework_advantage', 'exam_advantage', 'consistent'],
                                     size=n_cheaters, p=[0.5, 0.3, 0.2])

    # Apply different patterns based on cheater type
    for i, cheater_type in enumerate(cheater_types):
        if cheater_type == 'coursework_advantage':
            # Coursework performance much higher than expected from ability
            cheaters.loc[i, 'coursework_raw'] = cheaters.loc[i, 'ability'] + np.random.uniform(1.0, 2.5)
            cheaters.loc[i, 'exam_raw'] = cheaters.loc[i, 'ability'] + np.random.normal(0, 0.8)

        elif cheater_type == 'exam_advantage':
            # Exam performance much higher than expected from ability
            cheaters.loc[i, 'coursework_raw'] = cheaters.loc[i, 'ability'] + np.random.normal(0, 0.8)
            cheaters.loc[i, 'exam_raw'] = cheaters.loc[i, 'ability'] + np.random.uniform(1.5, 3.0)

        else:  # consistent
            # Suspiciously consistent high performance across both
            both_boost = np.random.uniform(1.0, 2.0)
            cheaters.loc[i, 'coursework_raw'] = cheaters.loc[i, 'ability'] + both_boost + np.random.normal(0, 0.2)
            cheaters.loc[i, 'exam_raw'] = cheaters.loc[i, 'ability'] + both_boost + np.random.normal(0, 0.2)

    # Combine datasets
    data = pd.concat([non_cheaters, cheaters]).reset_index(drop=True)

    # Generate other meaningful features

    # Subject variation (cheaters often have less variation)
    n_subjects = 5
    subject_scores = np.zeros((n_samples, n_subjects))

    for i in range(n_samples):
        base_ability = data.loc[i, 'ability']
        if data.loc[i, 'cheater'] == 0:
            # Non-cheaters: performance varies by subject
            subject_scores[i] = base_ability + np.random.normal(0, 1, n_subjects)
        else:
            # Cheaters: performance varies less in subjects they cheat in
            if np.random.random() < 0.7:  # 70% of cheaters have less subject variation
                subject_scores[i] = base_ability + np.random.normal(0, 0.4, n_subjects)
            else:
                subject_scores[i] = base_ability + np.random.normal(0, 1, n_subjects)

    data['subject_variation'] = np.std(subject_scores, axis=1)

    # Historical trend (cheaters may show sudden improvements)
    past_performance = data['ability'] + np.random.normal(0, 0.5, n_samples)
    current_performance = (data['coursework_raw'] + data['exam_raw']) / 2

    # Add sudden improvement for some cheaters
    cheater_indices = data[data['cheater'] == 1].index
    sudden_improvers = np.random.choice(cheater_indices, size=int(len(cheater_indices) * 0.6), replace=False)
    for idx in sudden_improvers:
        past_performance[idx] -= np.random.uniform(0.5, 1.5)  # Make past performance worse

    data['historical_trend'] = current_performance - past_performance

    # Time spent features (many cheaters finish suspiciously quickly or slowly)
    data['exam_time_std'] = np.random.normal(0, 1, n_samples)
    for i in cheater_indices:
        if np.random.random() < 0.4:
            # Some cheaters finish very quickly (had answers)
            data.loc[i, 'exam_time_std'] = -np.random.uniform(1.5, 3)
        elif np.random.random() < 0.7:
            # Some cheaters take unusually long (looking up answers)
            data.loc[i, 'exam_time_std'] = np.random.uniform(1.5, 3)

    # Peer comparison (performance relative to peer group)
    ability_percentiles = np.percentile(data['ability'], [33, 66])
    ability_groups = np.digitize(data['ability'], bins=ability_percentiles)

    # Fix: Changed the range to include 0, 1 and 2 for ability groups
    avg_group_exam = {i: data.loc[ability_groups == i, 'exam_raw'].mean() for i in range(0, 3)}
    data['peer_comparison'] = 0.0

    for i in range(n_samples):
        group = ability_groups[i]
        expected_score = avg_group_exam[group]
        data.loc[i, 'peer_comparison'] = data.loc[i, 'exam_raw'] - expected_score

    # Calculate standard z-scores
    data['coursework_z'] = (data['coursework_raw'] - data['coursework_raw'].mean()) / data['coursework_raw'].std()
    data['exam_z'] = (data['exam_raw'] - data['exam_raw'].mean()) / data['exam_raw'].std()
    data['z_diff'] = data['coursework_z'] - data['exam_z']

    # Score variance (consistency across different assessments)
    for i in range(n_samples):
        if data.loc[i, 'cheater'] == 1:
            # Generate more assessments
            if np.random.random() < 0.7:  # 70% of cheaters have suspicious consistency
                assessments = data.loc[i, 'ability'] + np.random.normal(1.2, 0.3, 8)  # low variance, high mean
            else:
                assessments = data.loc[i, 'ability'] + np.random.normal(0, 1, 8)
        else:
            assessments = data.loc[i, 'ability'] + np.random.normal(0, 1, 8)

        data.loc[i, 'score_variance'] = np.std(assessments)

    # Add anomaly score using Isolation Forest on legitimate features
    features_for_anomaly = ['coursework_z', 'exam_z', 'z_diff', 'score_variance',
                           'subject_variation', 'historical_trend']

    iso_forest = IsolationForest(contamination=0.2, random_state=42)
    anomaly_scores = iso_forest.fit_predict(data[features_for_anomaly])
    data['anomaly_score'] = anomaly_scores

    # Convert anomaly scores to a more intuitive scale (higher = more anomalous)
    data['anomaly_score'] = (data['anomaly_score'] == -1).astype(float)

    # Drop intermediate columns that wouldn't be available in real data
    final_data = data.drop(['ability', 'coursework_raw', 'exam_raw'], axis=1)

    return final_data

# Generate improved data
improved_data = generate_realistic_cheating_data(n_samples=1000, cheater_ratio=0.15)

# Splitting data
X = improved_data[['coursework_z', 'exam_z', 'z_diff', 'score_variance', 'exam_time_std', 'peer_comparison', 'subject_variation', 'historical_trend', 'anomaly_score']]
y = improved_data['cheater']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Balancing dataset using SMOTE
smote = SMOTE(random_state=42)
X_train_balanced, y_train_balanced = smote.fit_resample(X_train, y_train)

# Scaling the features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train_balanced)
X_test_scaled = scaler.transform(X_test)

# Compute class weights
class_weights = compute_class_weight(class_weight='balanced', classes=np.unique(y_train_balanced), y=y_train_balanced)
class_weights_dict = {0: class_weights[0], 1: class_weights[1]}

# Save processed data, scaler, and class weights (needed for loading)
joblib.dump(X_train_scaled, 'X_train_scaled.joblib')
joblib.dump(X_test_scaled, 'X_test_scaled.joblib')
joblib.dump(y_train_balanced, 'y_train_balanced.joblib')
joblib.dump(y_test, 'y_test.joblib')
joblib.dump(scaler, 'scaler.joblib')
joblib.dump(class_weights_dict, 'class_weights_dict.joblib')
print("Data, scaler, and class weights saved.")

"""# **Grid Search and Model Training**"""

# %%
# Grid Search and Model Training
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import fbeta_score
import joblib

# Load the training data, and class weights
X_train_scaled = joblib.load('X_train_scaled.joblib')
y_train_balanced = joblib.load('y_train_balanced.joblib')
class_weights_dict = joblib.load('class_weights_dict.joblib')
# Hyperparameter tuning with GridSearchCV
param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [10, 20, None],
    'min_samples_split': [2, 5, 10],
    'min_samples_leaf': [1, 2, 4],
    'max_features': ['sqrt', 'log2']
}

rf_clf_weighted = RandomForestClassifier(class_weight=class_weights_dict, random_state=42)
grid_search = GridSearchCV(estimator=rf_clf_weighted, param_grid=param_grid, cv=3, scoring='f1', n_jobs=-1)
grid_search.fit(X_train_scaled, y_train_balanced)

# Best hyperparameters
best_params = grid_search.best_params_
print(f"Best Hyperparameters: {best_params}")

# Train the final model with best hyperparameters
rf_clf_best = RandomForestClassifier(**best_params, class_weight=class_weights_dict, random_state=42)
rf_clf_best.fit(X_train_scaled, y_train_balanced)

# Save the model
joblib.dump(rf_clf_best, 'cheating_detection_model.pkl')
print("Model saved as cheating_detection_model.pkl")

# Determine optimal threshold
X_test_scaled = joblib.load('X_test_scaled.joblib')
y_test = joblib.load('y_test.joblib')
y_probs = rf_clf_best.predict_proba(X_test_scaled)[:, 1]
thresholds = np.linspace(0, 1, 100)
best_threshold = 0.5
best_f1 = 0
for threshold in thresholds:
    y_pred = (y_probs > threshold).astype(int)
    f1 = fbeta_score(y_test, y_pred, beta=1)
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = threshold
print(f"Best Threshold: {best_threshold}")

joblib.dump(best_threshold, 'best_threshold.joblib')
print("Best threshold saved.")

"""# **Model Loading and Analysis**"""

# Model Loading and Analysis
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import seaborn as sns


def analyze_student_with_dashboard(student_id, student_data, model, feature_names, threshold):
    """Analyzes a specific student and provides a prediction and radar chart."""

    # Convert single student data to a DataFrame
    student_df = pd.DataFrame([student_data], columns=feature_names)

    # Get model prediction probabilities
    prob = model.predict_proba(student_df)[:, 1][0]
    prediction = 1 if prob > threshold else 0

    # Create a radar chart (optional)
    radar_fig = plt.figure(figsize=(6,6))
    categories = feature_names
    values = student_data

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    values = np.append(values, values[0])  # Loop back to start
    angles += angles[:1]

    ax = radar_fig.add_subplot(111, polar=True)
    ax.fill(angles, values, color='blue', alpha=0.25)
    ax.plot(angles, values, color='blue', linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)

    # Generate report
    report = f"""
    Student ID: {student_id}
    Predicted Probability: {prob:.2f}
    Prediction: {'Cheater' if prediction else 'Not Cheater'}
    """

    return prediction, report, {'radar_chart': radar_fig}

# Load the model, scaler, and threshold
rf_clf_best = joblib.load('cheating_detection_model.pkl')
scaler = joblib.load('scaler.joblib')
best_threshold = joblib.load('best_threshold.joblib')

# Prepare data for analysis (using the same features as during training)
X = improved_data[['coursework_z', 'exam_z', 'z_diff', 'score_variance', 'exam_time_std', 'peer_comparison', 'subject_variation', 'historical_trend', 'anomaly_score']]
feature_names = X.columns.tolist()

X_test_scaled = joblib.load('X_test_scaled.joblib')
y_test = joblib.load('y_test.joblib')

# Evaluate the model on the test set
y_probs = rf_clf_best.predict_proba(X_test_scaled)[:, 1]
y_pred = (y_probs > best_threshold).astype(int)
print("Classification Report:\n", classification_report(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

# Visualize predicted probabilities
plt.figure(figsize=(10, 6))
sns.histplot(y_probs[y_test == 0], color="skyblue", label="Not Cheater", kde=True)
sns.histplot(y_probs[y_test == 1], color="coral", label="Cheater", kde=True)
plt.title("Distribution of Predicted Probabilities")
plt.xlabel("Predicted Probability (Cheater)")
plt.ylabel("Frequency")
plt.legend()
plt.savefig('predicted_probabilities_histogram.png') # Added saving
plt.show()

# Feature Importance Analysis
feature_importances = pd.Series(rf_clf_best.feature_importances_, index=feature_names)
print("\nFeature Importances:")
print(feature_importances.sort_values(ascending=False))
print("\nDescriptive statistics of feature importances:")
print(feature_importances.describe())

# Example usage: Analyze a sample student
student_index = 190
student_data = X_test_scaled[student_index]
prediction, report, figures = analyze_student_with_dashboard(
    student_id=student_index,
    student_data=student_data,
    model=rf_clf_best,
    feature_names=feature_names,
    threshold=best_threshold,
)
print(report)
if 'radar_chart' in figures:
    figures['radar_chart'].savefig('radar_chart.png')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import seaborn as sns

def analyze_student(student_id, student_data, model, feature_names, threshold):
    """Analyzes a specific student and provides a prediction along with feature contributions and radar chart."""

    # Convert single student data to a DataFrame
    student_df = pd.DataFrame([student_data], columns=feature_names)

    # Get model prediction probabilities
    prob = model.predict_proba(student_df)[:, 1][0]
    prediction = 1 if prob > threshold else 0

    # Feature contributions
    feature_contributions = dict(zip(feature_names, model.feature_importances_ * student_data))

    # Create a radar chart
    radar_fig = plt.figure(figsize=(6, 6))
    categories = feature_names
    values = student_data

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    values = np.append(values, values[0])  # Loop back to start
    angles += angles[:1]

    ax = radar_fig.add_subplot(111, polar=True)
    ax.fill(angles, values, color='blue', alpha=0.25)
    ax.plot(angles, values, color='blue', linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)

    return prediction, prob, feature_contributions, radar_fig

# Load the model and scaler
rf_clf_best = joblib.load('cheating_detection_model.pkl')
scaler = joblib.load('scaler.joblib')

# Load the test data
X_test_scaled = joblib.load('X_test_scaled.joblib')
y_test = joblib.load('y_test.joblib')

from sklearn.metrics import precision_recall_curve

precisions, recalls, thresholds = precision_recall_curve(y_test, y_probs)

# Find the threshold that balances precision and recall
best_idx = (precisions + recalls).argmax()
optimal_threshold = thresholds[best_idx]

print(f"Optimal threshold found: {optimal_threshold:.2f}")

# Apply the new threshold
y_pred_optimal = (y_probs > optimal_threshold).astype(int)

print("\nClassification Report (Optimal Threshold):\n", classification_report(y_test, y_pred_optimal))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_optimal))

# Prepare data for analysis
X = improved_data[['coursework_z', 'exam_z', 'z_diff', 'score_variance', 'exam_time_std', 'peer_comparison', 'subject_variation', 'historical_trend', 'anomaly_score']]
feature_names = X.columns.tolist()

# Evaluate the model on the test set
y_probs = rf_clf_best.predict_proba(X_test_scaled)[:, 1]
y_pred = (y_probs > optimal_threshold).astype(int)
print("Classification Report:\n", classification_report(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

# Visualize predicted probabilities
plt.figure(figsize=(10, 6))
sns.histplot(y_probs[y_test == 0], color="skyblue", label="Not Cheater", kde=True)
sns.histplot(y_probs[y_test == 1], color="coral", label="Cheater", kde=True)
plt.title("Distribution of Predicted Probabilities")
plt.xlabel("Predicted Probability (Cheater)")
plt.ylabel("Frequency")
plt.legend()
plt.show()

# Feature Importance Analysis
feature_importances = pd.Series(rf_clf_best.feature_importances_, index=feature_names)
print("\nFeature Importances:")
print(feature_importances.sort_values(ascending=False))
print("\nDescriptive statistics of feature importances:")
print(feature_importances.describe())

# List all students likely cheating
likely_cheaters = []
for student_index in range(X_test_scaled.shape[0]):
    student_data = X_test_scaled[student_index]
    prediction, prob, feature_contributions, radar_fig = analyze_student(
        student_id=student_index,
        student_data=student_data,
        model=rf_clf_best,
        feature_names=feature_names,
        threshold=optimal_threshold,
    )
    if prediction == 1:
        likely_cheaters.append({
            'Student ID': student_index,
            'Predicted Probability': prob,
            'Feature Contributions': feature_contributions,
            'Radar Chart': radar_fig
        })

# Convert the list of likely cheaters to a DataFrame
cheaters_df = pd.DataFrame(likely_cheaters)

# Generate a summary table
summary_table = cheaters_df[['Student ID', 'Predicted Probability']]
print("\nSummary Table: Students Likely Cheating\n")
print(summary_table)

# Summary statistics
print("\nSummary Statistics of Cheaters' Predicted Probabilities:\n")
print(cheaters_df['Predicted Probability'].describe())

# Display detailed analysis for each cheater
for index, row in cheaters_df.iterrows():
    print(f"\nDetailed Analysis for Student ID {row['Student ID']}:\n")
    print(f"Predicted Probability: {row['Predicted Probability']:.2f}")
    print("Feature Contributions:")
    for feature, contribution in row['Feature Contributions'].items():
        print(f"  {feature}: {contribution:.2f}")
    row['Radar Chart'].show()

# Summary distribution chart for all cheaters
plt.figure(figsize=(10, 6))
sns.histplot(cheaters_df['Predicted Probability'], color="coral", kde=True)
plt.title("Distribution of Predicted Probabilities for Cheaters")
plt.xlabel("Predicted Probability")
plt.ylabel("Frequency")
plt.show()

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import seaborn as sns

def analyze_student(student_id, student_data, model, feature_names, threshold):
    """Analyzes a specific student and provides a prediction along with feature contributions and radar chart."""

    # Convert single student data to a DataFrame
    student_df = pd.DataFrame([student_data], columns=feature_names)

    # Get model prediction probabilities
    prob = model.predict_proba(student_df)[:, 1][0]
    prediction = 1 if prob > threshold else 0

    # Feature contributions
    feature_contributions = dict(zip(feature_names, model.feature_importances_ * student_data))

    return prediction, prob, feature_contributions

# Load the model and scaler
rf_clf_best = joblib.load('cheating_detection_model.pkl')
scaler = joblib.load('scaler.joblib')

# Load the test data
X_test_scaled = joblib.load('X_test_scaled.joblib')
y_test = joblib.load('y_test.joblib')

from sklearn.metrics import precision_recall_curve

precisions, recalls, thresholds = precision_recall_curve(y_test, y_probs)

# Find the threshold that balances precision and recall
best_idx = (precisions + recalls).argmax()
optimal_threshold = thresholds[best_idx]

print(f"Optimal threshold found: {optimal_threshold:.2f}")

# Apply the new threshold
y_pred_optimal = (y_probs > optimal_threshold).astype(int)

print("\nClassification Report (Optimal Threshold):\n", classification_report(y_test, y_pred_optimal))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred_optimal))

# Prepare data for analysis
X = improved_data[['coursework_z', 'exam_z', 'z_diff', 'score_variance', 'exam_time_std', 'peer_comparison', 'subject_variation', 'historical_trend', 'anomaly_score']]
feature_names = X.columns.tolist()

# Evaluate the model on the test set
y_probs = rf_clf_best.predict_proba(X_test_scaled)[:, 1]
y_pred = (y_probs > optimal_threshold).astype(int)
print("Classification Report:\n", classification_report(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

# Initialize a list to store student data
students_list = []

# Analyze each student and store the results
for student_index in range(X_test_scaled.shape[0]):
    student_data = X_test_scaled[student_index]
    prediction, prob, feature_contributions = analyze_student(
        student_id=student_index,
        student_data=student_data,
        model=rf_clf_best,
        feature_names=feature_names,
        threshold=optimal_threshold,
    )
    students_list.append({
        'Student ID': student_index,
        'Predicted Probability': prob,
        'Cheater': 'Yes' if prediction == 1 else 'No'
    })

# Convert the list of students to a DataFrame
students_df = pd.DataFrame(students_list)

# Generate a summary table
summary_table = students_df[['Student ID', 'Predicted Probability', 'Cheater']]
print("\nSummary Table: Full List of Students (Cheaters Highlighted)\n")
print(summary_table)

# Highlight cheaters
# Changed the lambda to apply style for each column
highlighted_table = summary_table.style.apply(
    lambda x: ['background-color: blue' if x['Cheater'] == 'Yes' else '' for _ in x], axis=1
)
display(highlighted_table)
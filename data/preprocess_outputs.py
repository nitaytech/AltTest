import json
import os
from typing import Dict, Any
import re


def parse_json_like(input_string: str) -> Dict:
    init_string = input_string

    def find_substrings(input_string):
        patterns = [r': "(.*?)",\n', r': "(.*?)"\n}', r': \'(.*?)\',\n', r': \'(.*?)\'\n}']
        matches = []
        for pattern in patterns:
            matches += re.findall(pattern, input_string)
        return matches

    if input_string is None:
        return None
    if '```json' in input_string:
        input_string = input_string[input_string.find('```json')+7:]
    if '```' in input_string:
        input_string = input_string[:input_string.find('```') + 3]
    input_string = input_string.replace('```json', '').replace('```', '').strip()
    input_string = input_string.replace(': true', ': True').replace(': false', ': False')
    input_string = input_string.replace(': "true"', ': True').replace(': "false"', ': False')
    input_string = input_string.replace(': \'true\'', ': True').replace(': \'false\'', ': False')
    input_string = input_string.replace(': `true`', ': True').replace(': `false`', ': False')

    if '\"Explanation\":' in input_string and '\"Answer\":' in input_string:
        explanation_index = input_string.index('\"Explanation\":')
        answer_index = input_string.index('\"Answer\":')
        last_quote_index = explanation_index + input_string[explanation_index:answer_index].rfind('"')
        if ',' not in input_string[last_quote_index:answer_index]:
            input_string = input_string[:last_quote_index + 1] + ',' + input_string[last_quote_index + 1:]

    try:
        return eval(input_string)
    except Exception as e:
        values = find_substrings(input_string)
        for value in values:
            escaped_value = value.replace('"', '\\"').replace("'", "\\'")
            input_string = input_string.replace(value, escaped_value)
        try:
            return eval(input_string)
        except Exception as e:
            possible_labels = ['Negative', 'Positive', 'unknown', 'Yes', 'No', 'Partially',
                               'Irrelevant', 'Ignore', 'HasProperty', 'PartOf', 'Material-MadeOf', 'Emotion-Evaluation',
                               'Time', 'Location', 'Function', 'Has-Prerequisite', 'Result-In', 'Action', 'Thematic',
                               'Category-Exemplar-Pairs', 'Members-of-the-same-Category', 'Synonym', 'Antonym',
                               'Common-Phrase', 'None-of-the-above', 'model_a', 'model_b', 'tie', 'yes', 'no']
            for label in possible_labels:
                if label.lower() == 'no':
                    if ((': no' in input_string or ': No' in input_string) and
                            not (': "no"' in input_string or ': \'no\'' in input_string) and
                            not (': "No"' in input_string or ': \'No\'' in input_string) and
                            not (': None' in input_string or ': none' in input_string)):
                        input_string = input_string.replace(f': {label}', f': "{label}"')
                elif label in input_string and not (f'"{label}"' in input_string or f"'{label}'" in input_string):
                    input_string = input_string.replace(label, f'"{label}"')
            try:
                return eval(input_string)
            except Exception as e:
                return input_string


def process_cebab(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = [1, 2, 3, 4, 5, 'Negative', 'Positive', 'unknown']
    total = 0
    failures = 0
    questions = ['ambiance', 'food', 'noise', 'service', 'stars']
    for item_id, prediction in predictions.items():
        item_predictions = {q: 'unknown' if q != 'stars' else 3 for q in questions}
        for q in questions:
            total += 1
            if prediction is None or not isinstance(prediction, dict) or q not in prediction:
                failures += 1
            else:
                pred = prediction[q]
                if pred == 'Unknown':
                    pred = 'unknown'
                if q == 'stars':
                    if isinstance(pred, str) and not pred.isdigit():
                        failures += 1
                    else:
                        pred = int(pred)
                else:
                    possible_label_for_pred = [l for l in possible_labels if isinstance(l, str) and l.lower() == pred.lower()]
                    if len(possible_label_for_pred) != 0:
                        pred = possible_label_for_pred[0]
                    else:
                        failures += 1
                if pred not in possible_labels:
                    failures += 1
                else:
                    item_predictions[q] = pred
        for q, pred in item_predictions.items():
            annotations[item_id + '__' + q] = pred
    print(f'\tFailures: {failures}/{total}\tTotal: {len(annotations)}')
    return annotations


def process_lgbteen(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = ['Yes', 'No', 'Partially', 'Irrelevant', 'Ignore']
    failures = 0
    for item_id, prediction in predictions.items():
        if prediction is None or not isinstance(prediction, dict) or 'Answer' not in prediction:
            if isinstance(prediction, str) and prediction.lower() in [l.lower() for l in possible_labels]:
                pred = [l for l in possible_labels if l.lower() == prediction.lower()][0]
            else:
                pred = 'No'
                failures += 1
        else:
            pred = prediction['Answer']
        if pred not in possible_labels:
            annotations[item_id] = 'No'
            failures += 1
        else:
            annotations[item_id] = pred
    print(f'\tFailures: {failures}/{len(predictions)}\tTotal: {len(annotations)}')
    return annotations


def process_wax(predictions: Dict[str, str]) -> Dict[str, Any]:
    def fix_wax_label(label):
        return label.replace('-', '').replace(' ', '').lower()
    annotations = {}
    possible_labels = ['HasProperty', 'PartOf', 'Material-MadeOf', 'Emotion-Evaluation', 'Time', 'Location',
                       'Function', 'Has-Prerequisite', 'Result-In', 'Action', 'Thematic',
                       'Category-Exemplar-Pairs', 'Members-of-the-same-Category', 'Synonym', 'Antonym',
                       'Common-Phrase', 'None-of-the-above']
    fixed_to_original = {fix_wax_label(label): label for label in possible_labels}
    possible_labels = [fix_wax_label(label) for label in possible_labels]
    failures = 0
    for item_id, prediction in predictions.items():
        if prediction is None or not isinstance(prediction, dict) or 'relation' not in prediction:
            pred = 'synonym'
            failures += 1
        else:
            pred = fix_wax_label(prediction['relation'])
        if pred not in possible_labels:
            annotations[item_id] = fixed_to_original['synonym']
            failures += 1
        else:
            annotations[item_id] = fixed_to_original[pred]
    print(f'\tFailures: {failures}/{len(predictions)}\tTotal: {len(annotations)}')
    return annotations


def process_framing(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = ['yes', 'no']
    total = 0
    failures = 0
    questions = {
        'co': ['co1', 'co2', 'co3', 'co4'],
        'ec': ['ec1', 'ec2', 'ec3'],
        're': ['re1', 're2', 're3', 're4', 're5', 're6', 're7'],
        'mo': ['mo1', 'mo2', 'mo3'],
        'hi': ['hi1', 'hi2', 'hi3', 'hi4', 'hi5']
    }
    for item_id, prediction in predictions.items():
        question = item_id.split('__')[-1]
        item_questions = questions[question]
        item_predictions = {q: 'no' for q in item_questions}
        for q in item_questions:
            total += 1
            if prediction is None or not isinstance(prediction, dict) or q not in prediction:
                failures += 1
            else:
                pred = prediction[q]
                if pred not in possible_labels:
                    failures += 1
                else:
                    item_predictions[q] = pred
        for q, pred in item_predictions.items():
            annotations[item_id.replace('____', '__') + q[2:]] = pred
    print(f'\tFailures: {failures}/{total}\tTotal: {len(annotations)}')
    return annotations


def process_summeval(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = [1, 2, 3, 4, 5]
    total = 0
    failures = 0
    questions = ['coherence', 'consistency', 'relevance', 'fluency']
    for item_id, prediction in predictions.items():
        item_predictions = {q: 3 for q in questions}
        for q in questions:
            total += 1
            if prediction is None or not isinstance(prediction, dict) or q not in prediction:
                failures += 1
            else:
                pred = prediction[q]
                if isinstance(pred, str) and not pred.isdigit():
                    failures += 1
                else:
                    pred = int(pred)
                    if pred not in possible_labels:
                        failures += 1
                    else:
                        item_predictions[q] = pred
        for q, pred in item_predictions.items():
            annotations[item_id + '__' + q] = pred
    print(f'\tFailures: {failures}/{total}\tTotal: {len(annotations)}')
    return annotations


def process_mtbench(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = ['model_a', 'model_b', 'tie']
    failures = 0
    for item_id, prediction in predictions.items():
        if prediction is None or not isinstance(prediction, dict) or 'winner' not in prediction:
            pred = 'model_a'
            failures += 1
        else:
            pred = prediction['winner']
        if pred not in possible_labels:
            annotations[item_id] = 'model_a'
            failures += 1
        else:
            annotations[item_id] = pred
    print(f'\tFailures: {failures}/{len(predictions)}\tTotal: {len(annotations)}')
    return annotations


def process_10k_prompts(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = [1, 2, 3, 4, 5]
    failures = 0
    for item_id, prediction in predictions.items():
        if prediction is None or not isinstance(prediction, dict) or 'quality' not in prediction:
            pred = 3
            failures += 1
        else:
            pred = int(prediction['quality'])
        if pred not in possible_labels:
            annotations[item_id] = 3
            failures += 1
        else:
            annotations[item_id] = pred
    print(f'\tFailures: {failures}/{len(predictions)}\tTotal: {len(annotations)}')
    return annotations


def process_lesion(predictions: Dict[str, str]) -> Dict[str, Any]:
    annotations = {}
    possible_labels = [0, 1, 2, 3, 4, 5, 6]
    total = 0
    failures = 0
    questions = ['Asymmetry', 'Blue', 'Border', 'Color', 'Dermo']
    for item_id, prediction in predictions.items():
        item_predictions = {q: 1 for q in questions}
        for q in questions:
            total += 1
            if prediction is None or not isinstance(prediction, dict) or q not in prediction:
                failures += 1
            else:
                pred = prediction[q]
                if isinstance(pred, str) and not pred.isdigit():
                    failures += 1
                else:
                    pred = int(pred)
                    if pred not in possible_labels:
                        failures += 1
                    else:
                        item_predictions[q] = pred
        for q, pred in item_predictions.items():
            annotations[item_id + '__' + q] = pred
    print(f'\tFailures: {failures}/{total}\tTotal: {len(annotations)}')
    return annotations


def process_kilogram(predictions: Dict[str, str]) -> Dict[str, Any]:
    failures = 0
    annotations = {}
    for item_id, pred in predictions.items():
        if isinstance(pred, str):
            annotations[item_id] = pred.lower().replace('.', '').strip()
        else:
            failures += 1
            annotations[item_id] = 'unknown'
    print(f'\tFailures: {failures}/{len(predictions)}\tTotal: {len(annotations)}')
    return annotations

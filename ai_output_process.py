def sort_by_score(elem):
    if elem.get("Score", None):
        return float(elem["Score"][:-1])
    else:
        return float(elem["score"])


def most_likely_emotion(emotions):
    if len(emotions) > 0:
        return emotions[0]
    return {"Emotion": "Neutral", "Score": "100%"}
    # only return the emotion with the highest score if it is above 50%
    # if len(emotions) > 0:
    #     if float(emotions[0]["Score"][:-1]) > 50:
    #         return emotions[0]
    #     else:
    #         return {"Emotion": "Neutral", "Score": "100%"}
    # else:
    #     return {"Emotion": "Neutral", "Score": "100%"}


def get_best_fitting_output(text, dictionary):
    result = ""
    i = 0
    if text:
        while i < len(text):
            # Check for a two-character match
            if i + 1 < len(text) and text[i:i + 2] in dictionary:
                result += dictionary[text[i:i + 2]] + "|"
                i += 2
            # Check for a one-character match
            elif text[i] in dictionary:
                result += dictionary[text[i]] + "|"
                i += 1
            # If no match found, append the original character
            else:
                # print(f"No match found for {text[i]}")
                # result += text[i]
                i += 1
    return result


def get_best_fitting_output_from_list(input_list, dictionary):
    result = []
    for text in input_list:
        if text is None:
            # Handle None values by using a default "rest" phoneme
            result.append("rest")
        elif text == " " or text == "h#":
            result.append("rest")
        else:
            try:
                # Safely handle text processing
                text_str = str(text).strip()
                result.append(dictionary.get(text_str, text_str.upper()))
            except (AttributeError, TypeError):
                # If any error occurs, use a default value
                import logging
                logging.warning(f"Error processing phoneme: {text}")
                result.append("rest")
    return result

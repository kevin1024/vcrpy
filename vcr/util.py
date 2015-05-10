def partition_dict(predicate, dictionary):
    true_dict = {}
    false_dict = {}
    for key, value in dictionary.items():
        this_dict = true_dict if predicate(key, value) else false_dict
        this_dict[key] = value
    return true_dict, false_dict


def compose(*functions):
    def composed(incoming):
        res = incoming
        for function in functions[::-1]:
            res = function(res)
        return res
    return composed

class Datasets:
    @staticmethod
    def load(name, rows):
        processor_name = f"_process_{name}"
        processor = getattr(Datasets, processor_name)
        return processor(rows)

    @staticmethod
    def _process_gsm8k(rows):
        return rows

    @staticmethod
    def _process_coin(rows):
        return rows[::-1]

    @staticmethod
    def _unrelated(rows):
        return None

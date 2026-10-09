class Strategy:
    name = "Base"
    description = ""

    def prepare(self, df):
        return df.copy()

    def generate_signal(self, df, i):
        raise NotImplementedError

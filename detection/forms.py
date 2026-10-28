from django import forms


class UploadForm(forms.Form):
    csv_file = forms.FileField(
        label='Transaction CSV File',
        help_text='Upload a CSV file containing transaction records for fraud detection.',
        widget=forms.ClearableFileInput(attrs={'accept': '.csv'}),
    )

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']
        if not f.name.endswith('.csv'):
            raise forms.ValidationError('Only CSV files are accepted.')
        if f.size > 100 * 1024 * 1024:  # 100 MB
            raise forms.ValidationError('File size must be under 100 MB.')
        return f

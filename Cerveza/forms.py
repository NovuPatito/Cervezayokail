from django import forms
from .models import Cerveza, Resena

class CervezaForm(forms.ModelForm):
    class Meta:
        model = Cerveza
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:  # Si es una edición
            self.fields['stock'].required = False
            self.fields['stock'].widget = forms.HiddenInput()

class ResenaForm(forms.ModelForm):
    class Meta:
        model = Resena
        fields = ['nombre', 'puntuacion', 'comentario']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tu nombre'
            }),
            'puntuacion': forms.NumberInput(attrs={
                'type': 'range',
                'min': '1',
                'max': '5',
                'step': '1',
                'class': 'form-range',
                'id': 'ratingInput'
            }),
            'comentario': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Escribe tu reseña...'
            })
        }
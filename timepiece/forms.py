from django import forms
from timepiece.models import Project, Activity, Entry
from timepiece.fields import PendulumDateTimeField
from timepiece.widgets import PendulumDateTimeWidget
from datetime import datetime

from timepiece import models as timepiece
from crm import models as crm


class ClockInForm(forms.Form):
    """
    Allow users to clock in
    """

    project = forms.ModelChoiceField(queryset=Project.objects.all())

class ClockOutForm(forms.Form):
    """
    Allow users to clock out
    """

    activity = forms.ModelChoiceField(queryset=Activity.objects.all(),
                                      required=False)
    comments = forms.CharField(widget=forms.Textarea,
                               required=False)

class AddUpdateEntryForm(forms.ModelForm):
    """
    This form will provide a way for users to add missed log entries and to
    update existing log entries.
    """

    start_time = forms.DateTimeField(
        widget=forms.SplitDateTimeWidget(attrs={'class': 'timepiece-time'})
    )
    end_time = forms.DateTimeField(
        widget=forms.SplitDateTimeWidget(attrs={'class': 'timepiece-time'})
    )

    #start_time = PendulumDateTimeField()
    #end_time = PendulumDateTimeField()

    class Meta:
        model = Entry
        exclude = ('user', 'pause_time', 'site', 'hours')

    def clean_start_time(self):
        """
        Make sure that the start time is always before the end time
        """
        start = self.cleaned_data['start_time']

        try:
            end = self.cleaned_data['end_time']

            if start >= end:
                raise forms.ValidationError('The entry must start before it ends!')
        except KeyError:
            pass

        if start > datetime.now():
            raise forms.ValidationError('You cannot add entries in the future!')

        return start

    def clean_end_time(self):
        """
        Make sure no one tries to add entries that end in the future
        """
        try:
            start = self.cleaned_data['start_time']
        except KeyError:
            raise forms.ValidationError('Please enter a start time.')

        try:
            end = self.cleaned_data['end_time']
            if not end: raise Exception
        except:
            raise forms.ValidationError('Please enter an end time.')

        if end > datetime.now():
            raise forms.ValidationError('You cannot clock out in the future!')

        if start >= end:
            raise forms.ValidationError('The entry must start before it ends!')

        return end

    #def clean(self):
    #    print self.cleaned_data


class DateForm(forms.Form):
    from_date = forms.DateField(label="From", required=False)
    to_date = forms.DateField(label="To", required=False)
    
    def save(self):
        return (
            self.cleaned_data.get('from_date', ''),
            self.cleaned_data.get('to_date', ''),
        )


class ProjectForm(forms.ModelForm):
    class Meta:
        model = timepiece.Project
        fields = (
            'name',
            'business',
            'trac_environment',
            'point_person',
            'type',
            'status',
            'description',
        )

    def __init__(self, *args, **kwargs):
        self.business = kwargs.pop('business')
        super(ProjectForm, self).__init__(*args, **kwargs)

        if self.business:
            self.fields.pop('business')
        else:
            self.fields['business'].queryset = crm.Contact.objects.filter(
                type='business',
                business_types__name='client',
            )

    def save(self):
        instance = super(ProjectForm, self).save(commit=False)
        if self.business:
            instance.business = self.business
        instance.save()
        return instance


class ProjectRelationshipForm(forms.ModelForm):
    class Meta:
        model = timepiece.ProjectRelationship
        fields = ('types',)

    def __init__(self, *args, **kwargs):
        super(ProjectRelationshipForm, self).__init__(*args, **kwargs)
        self.fields['types'].widget = forms.CheckboxSelectMultiple(
            choices=self.fields['types'].choices
        )
        self.fields['types'].help_text = ''


class RepeatPeriodForm(forms.ModelForm):
    class Meta:
        model = timepiece.RepeatPeriod
        fields = ('active', 'count', 'interval')

    def __init__(self, *args, **kwargs):
        super(RepeatPeriodForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            print 'hi'
            self.fields['date'] = forms.DateField()
            self.fieldOrder = ('active', 'count', 'interval', 'date')

    def _clean_optional(self, name):
        active = self.cleaned_data.get(name, False)
        value = self.cleaned_data.get(name, '')
        if active and not value:
            raise forms.ValidationError('This field is required.')
        return self.cleaned_data[name]
    
    def clean_count(self):
        return self._clean_optional('count')
    
    def clean_interval(self):
        return self._clean_optional('interval')
        
    def clean_date(self):
        return self._clean_optional('date')
    
    def save(self, project):
        period = super(RepeatPeriodForm, self).save(commit=False)
        period.project = project
        if not self.instance.id and period.active:
            period.save()
            period.billing_windows.create(
                date=self.cleaned_data['date'],
                end_date=self.cleaned_data['date'] + period.delta(),
            )
        elif self.instance.id:
            period.save()
        return period
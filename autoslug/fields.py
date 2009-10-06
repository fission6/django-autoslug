# -*- coding: utf-8 -*-
#
#  Copyright (c) 2008—2009 Andy Mikhailenko
#
#  This file is part of django-autoslug.
#
#  django-autoslug is free software under terms of the GNU Lesser
#  General Public License version 3 (LGPLv3) as published by the Free
#  Software Foundation. See the file README for copying conditions.
#

# python
from warnings import warn

# django
from django.db.models.fields import FieldDoesNotExist, DateField, SlugField

# app
from autoslug.settings import slugify


SLUG_INDEX_SEPARATOR = '-'    # the "-" in "foo-2"


class AutoSlugField(SlugField):
    """
    AutoSlugField is an extended SlugField able to automatically resolve name
    clashes.

    AutoSlugField can also perform the following tasks on save:

    - populate itself from another field (using `populate_from`),
    - use custom `slugify` function (using `slugify` or :doc:`settings`), and
    - preserve uniqueness of the value (using `unique` or `unique_with`).

    None of the tasks is mandatory, i.e. you can have auto-populated non-unique
    fields, manually entered unique ones (absolutely unique or within a given
    date) or both.

    Uniqueness is preserved by checking if the slug is unique with given constraints
    (`unique_with`) or globally (`unique`) and adding a number to the slug to make
    it unique.

    :param populate_from: string or callable: if string is given, it is considered
        as the name of attribute from which to fill the slug. If callable is given,
        it should accept `instance` parameter and return a value to fill the slug
        with.
    :param sep: string: if defined, overrides default separator for automatically
        incremented slug index (i.e. the "-" in "foo-2").
    :param slugify: callable: if defined, overrides `AUTOSLUG_SLUGIFY_FUNCTION`
        defined in :doc:`settings`.
    :param unique: boolean: ensure total slug uniqueness (unless more precise
        `unique_with` is defined).
    :param unique_with: string or tuple of strings: name or names of attributes
        to check for "partial uniqueness", i.e. there will not be two objects
        with identical slugs if these objects share the same values of given
        attributes. For instance, ``unique_with='pub_date'`` tells AutoSlugField
        to enforce slug uniqueness of all items published on given date. The
        slug, however, may reappear on another date. If more than one field is
        given, e.g. ``unique_with=('pub_date', 'author')``, then the same slug may
        reappear within a day or within some author's articles but never within
        a day for the same author. Foreign keys are also supported, i.e. not only
        `unique_with='author'` will do, but also `unique_with='author__name'`.

    .. note:: always place any slug attribute *after* attributes referenced
        by it (i.e. those from which you wish to `populate_from` or check
        `unique_with`). The reasoning is that autosaved dates and other such
        fields must be already processed before using them in the AutoSlugField.

    Example usage::

        from django.db import models
        from autoslug.fields import AutoSlugField

        class Article(models.Model):
            '''An article with title, date and slug. The slug is not totally
            unique but there will be no two articles with the same slug within
            any month.
            '''
            title = models.CharField(max_length=200)
            pub_date = models.DateField(auto_now_add=True)
            slug = AutoSlugField(populate_from='title', unique_with='pub_date__month')


    More options::

        # slugify but allow non-unique slugs
        slug = AutoSlugField()

        # globally unique, silently fix on conflict ("foo" --> "foo-1".."foo-n")
        slug = AutoSlugField(unique=True)

        # autoslugify value from attribute named "title"; editable defaults to False
        slug = AutoSlugField(populate_from='title')

        # same as above but force editable=True
        slug = AutoSlugField(populate_from='title', editable=True)

        # ensure that slug is unique with given date (not globally)
        slug = AutoSlugField(unique_with='pub_date')

        # ensure that slug is unique with given date AND category
        slug = AutoSlugField(unique_with=('pub_date','category'))

        # ensure that slug in unique with an external object
        # assuming that author=ForeignKey(Author)
        slug = AutoSlugField(unique_with='author')

        # ensure that slug in unique with a subset of external objects (by lookups)
        # assuming that author=ForeignKey(Author)
        slug = AutoSlugField(unique_with='author__name')

        # mix above-mentioned behaviour bits
        slug = AutoSlugField(populate_from='title', unique_with='pub_date')

        # minimum date granularity is shifted from day to month
        slug = AutoSlugField(populate_from='title', unique_with='pub_date__month')

        # autoslugify value from a dynamic attribute (i.e. a method)
        slug = AutoSlugField(populate_from='get_full_name')

        # autoslugify value from a custom callable
        # (ex. usage: user profile models)
        slug = AutoSlugField(populate_from=lambda instance: instance.user.get_full_name())

        # autoslugify value using custom `slugify` function
        from autoslug.settings import slugify as default_slugify
        def custom_slugify(value):
            return default_slugify(value).replace('-', '_')
        slug = AutoSlugField(slugify=custom_slugify)
    """
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 50)

        # autopopulated slug is not editable unless told so
        self.populate_from = kwargs.pop('populate_from', None)
        if self.populate_from:
            kwargs.setdefault('editable', False)

        # unique_with value can be string or tuple
        self.unique_with = kwargs.pop('unique_with', ())
        if isinstance(self.unique_with, basestring):
            self.unique_with = (self.unique_with,)

        self.slugify = kwargs.pop('slugify', slugify)
        assert hasattr(self.slugify, '__call__')

        self.index_sep = kwargs.pop('sep', SLUG_INDEX_SEPARATOR)

        # backward compatibility
        if kwargs.get('unique_with_date'):
            warn('Using unique_with_date="foo" in AutoSlugField is deprecated, '\
                 'use unique_with=("foo",) instead.', DeprecationWarning)
            self.unique_with += (kwargs['unique_with_date'],)

        if self.unique_with:
            # we will do "manual" granular check below
            kwargs['unique'] = False

        # Set db_index=True unless it's been set manually.
        if 'db_index' not in kwargs:
            kwargs['db_index'] = True
        super(SlugField, self).__init__(*args, **kwargs)

    def pre_save(self, instance, add):

        # get currently entered slug
        value = self.value_from_object(instance)

        # autopopulate (unless the field is editable and has some value)
        if self.populate_from and not value: # and not self.editable:
            value = self._get_prepopulated_value(instance)

            if __debug__ and not value:
                print 'Failed to populate slug %s.%s from %s' % \
                    (instance._meta.object_name, self.name, self.populate_from)

        slug = self.slugify(value)

        if not slug:
            # no incoming value,  use model name
            slug = instance._meta.module_name

        assert slug, 'slug is defined before trying to ensure uniqueness'

        # ensure the slug is unique (if required)
        if self.unique or self.unique_with:
            slug = self._generate_unique_slug(instance, slug)

        assert slug, 'value is filled before saving'

        # make the updated slug available as instance attribute
        setattr(instance, self.name, slug)

        return slug

    def _get_prepopulated_value(self, instance):
        """Returns preliminary value based on `populate_from`."""
        if callable(self.populate_from):
            # AutoSlugField(populate_from=lambda instance: ...)
            return self.populate_from(instance)
        else:
            # AutoSlugField(populate_from='foo')
            attr = getattr(instance, self.populate_from)
            return callable(attr) and attr() or attr

    def _generate_unique_slug(self, instance, slug):
        """
        Generates unique slug by adding a number to given value until no model
        instance can be found with such slug. If ``unique_with`` (a tuple of field
        names) was specified for the field, all these fields are included together
        in the query when looking for a "rival" model instance.
        """
        base_instance = instance

        def _get_lookups(instance, unique_with):
            "Returns a dict'able tuple of lookups to ensure slug uniqueness"
            for _field_name in unique_with:
                if '__' in _field_name:
                    field_name, inner = _field_name.split('__', 1)
                else:
                    field_name, inner = _field_name, None

                if not hasattr(instance, '_meta'):
                    raise ValueError('Could not resolve lookup "...%s" in %s.%s'
                                     ' `unique_with`.'
                                     % (_field_name, base_instance._meta.object_name,
                                        self.name))

                try:
                    field = instance._meta.get_field(field_name)
                except FieldDoesNotExist:
                    raise ValueError('Could not find attribute %s.%s referenced'
                                     ' by %s.%s (see constraint `unique_with`)'
                                     % (instance._meta.object_name, field_name,
                                        base_instance._meta.object_name, self.name))

                value = getattr(instance, field_name)
                if not value:
                    raise ValueError('Could not check uniqueness of %s.%s with'
                                     ' respect to %s.%s because the latter is empty.'
                                     ' Please ensure that "%s" is declared *after*'
                                     ' all fields it depends on (i.e. "%s"), and'
                                     ' that they are not blank.'
                                     % (base_instance._meta.object_name, self.name,
                                        instance._meta.object_name, field_name,
                                        self.name, '", "'.join(self.unique_with)))
                if isinstance(field, DateField):    # DateTimeField is a DateField subclass
                    inner = inner or 'day'

                    if '__' in inner:
                        raise ValueError('The `unique_with` constraint in %s.%s'
                                         ' is set to "%s", but AutoSlugField only'
                                         ' accepts one level of nesting for dates'
                                         ' (e.g. "date__month").'
                                         % (base_instance._meta.object_name, self.name,
                                            _field_name))

                    parts = ['year', 'month', 'day']
                    try:
                        granularity = parts.index(inner) + 1
                    except ValueError:
                        raise ValueError('expected one of %s, got "%s" in "%s"'
                                         % (parts, inner, _field_name))
                    else:
                        for part in parts[:granularity]:
                            lookup = '%s__%s' % (field_name, part)
                            yield lookup, getattr(value, part)
                else:
                    if inner:
                        for res in _get_lookups(value, [inner]):
                            yield _field_name, res[1]
                    else:
                        yield field_name, value

        lookups = tuple(_get_lookups(instance, self.unique_with))
        model = instance.__class__
        field_name = self.name
        index = 1
        if self.max_length < len(slug):
            slug = slug[:self.max_length]
        orig_slug = slug
        # keep changing the slug until it is unique
        while True:
            rivals = model.objects\
                          .filter(**dict(lookups + ((self.name, slug),) ))\
                          .exclude(pk=instance.pk)                              
            if not rivals:
                # the slug is unique, no model uses it
                return slug
                
            # the slug is not unique; change once more
            index += 1
            # ensure the resulting string is not too long
            tail_length = len(self.index_sep) + len(str(index))
            combined_length = len(orig_slug) + tail_length
            if self.max_length < combined_length:
                orig_slug = orig_slug[:self.max_length - tail_length]
            # re-generate the slug
            data = dict(slug=orig_slug, sep=self.index_sep, index=index)
            slug = '%(slug)s%(sep)s%(index)d' % data
            
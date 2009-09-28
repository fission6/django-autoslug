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

# TODO: test cases for dates and unique_with

from django.test import TestCase

from django.db.models import Model, CharField, ForeignKey
from autoslug.fields import AutoSlugField


class SimpleModel(Model):
    """
    >>> a = SimpleModel(name='test')
    >>> a.save()
    >>> a.slug
    'simplemodel'
    """
    name = CharField(max_length=200)
    slug = AutoSlugField()


class ModelWithUniqueSlug(Model):
    """
    >>> greeting = 'Hello world!'
    >>> a = ModelWithUniqueSlug(name=greeting)
    >>> a.save()
    >>> a.slug
    'hello-world'
    >>> b = ModelWithUniqueSlug(name=greeting)
    >>> b.save()
    >>> b.slug
    'hello-world-2'
    """
    name = CharField(max_length=200)
    slug = AutoSlugField(populate_from='name', unique=True)
    

class ModelWithUniqueSlugFK(Model):    
    """
    >>> sm1 = SimpleModel.objects.create(name='test')
    >>> sm2 = SimpleModel.objects.create(name='test')
    >>> sm3 = SimpleModel.objects.create(name='test2')    
    >>> greeting = 'Hello world!'
    >>> a = ModelWithUniqueSlugFK.objects.create(name=greeting, simple_model=sm1)
    >>> a.slug
    'hello-world'
    >>> b = ModelWithUniqueSlugFK.objects.create(name=greeting, simple_model=sm2)
    >>> b.slug
    'hello-world-2'
    >>> c = ModelWithUniqueSlugFK.objects.create(name=greeting, simple_model=sm3)
    >>> c.slug
    'hello-world'
    >>> d = ModelWithUniqueSlugFK.objects.create(name=greeting, simple_model=sm1)
    >>> d.slug
    'hello-world-3'
    """    
    name = CharField(max_length=200)
    simple_model = ForeignKey(SimpleModel)
    slug = AutoSlugField(populate_from='name', unique_with='simple_model__name')


class ModelWithLongName(Model):
    """
    >>> long_name = 'x' * 250
    >>> a = ModelWithLongName(name=long_name)
    >>> a.save()
    >>> len(a.slug)    # original slug is cropped by field length
    50
    >>> b = ModelWithLongName(name=long_name)
    >>> b.save()
    >>> b.slug[-3:]    # uniqueness is forced
    'x-2'
    >>> len(b.slug)    # slug is cropped
    50
    """
    name = CharField(max_length=200)
    slug = AutoSlugField(populate_from='name', unique=True)


class ModelWithCallable(Model):
    """
    >>> a = ModelWithCallable.objects.create(name='larch')
    >>> a.slug
    'the-larch'
    """
    name = CharField(max_length=200)
    slug = AutoSlugField(populate_from=lambda instance: u'the %s' % instance.name)


class ModelWithCallableAttr(Model):
    """
    >>> a = ModelWithCallableAttr.objects.create(name='albatross')
    >>> a.slug
    'spam-albatross-and-spam'
    """
    name = CharField(max_length=200)
    slug = AutoSlugField(populate_from='get_name')

    def get_name(self):
        return u'spam, %s and spam' % self.name


class ModelWithCustomPrimaryKey(Model):
    """
    # just check if models are created without exceptions
    >>> a = ModelWithCustomPrimaryKey.objects.create(custom_primary_key='a',
    ...                                              name='name used in slug')
    >>> b = ModelWithCustomPrimaryKey.objects.create(custom_primary_key='b',
    ...                                              name='name used in slug')
    >>> a.slug
    'name-used-in-slug'
    """
    custom_primary_key = CharField(primary_key=True, max_length=1)
    name = CharField(max_length=200)
    slug = AutoSlugField(populate_from='name', unique=True)

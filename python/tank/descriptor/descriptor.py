# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import copy

from ..util import filesystem
from .io_descriptor import create_io_descriptor
from .errors import TankDescriptorError
from ..util import LocalFileStorageManager

def create_descriptor(
        sg_connection,
        descriptor_type,
        dict_or_uri,
        bundle_cache_root_override=None,
        fallback_roots=None,
        resolve_latest=False,
        constraint_pattern=None):
    """
    Factory method. Use this when creating descriptor objects.

    :param sg_connection: Shotgun connection to associated site
    :param descriptor_type: Either ``Descriptor.APP``, ``CORE``, ``CONFIG``, ``ENGINE`` or ``FRAMEWORK``
    :param dict_or_uri: A std descriptor dictionary dictionary or string
    :param bundle_cache_root_override: Optional override for root path to where
                                       downloaded apps are cached. If not specified,
                                       the global bundle cache location will be used. This location is a per-user
                                       cache that is shared across all sites and projects.
    :param fallback_roots: Optional List of immutable fallback cache locations where
                           apps will be searched for. Note that when descriptors
                           download new content, it always ends up in the
                           bundle_cache_root.
    :param resolve_latest: If true, the latest version will be determined and returned.
                           If set to True, no version information need to be supplied with
                           the descriptor dictionary/uri. Please note that setting this flag
                           to true will typically affect performance - an external connection
                           is often required in order to establish what the latest version is.
    :param constraint_pattern: If resolve_latest is True, this pattern can be used to constrain
                           the search for latest to only take part over a subset of versions.
                           This is a string that can be on the following form:
                                - ``v0.1.2``, ``v0.12.3.2``, ``v0.1.3beta`` - a specific version
                                - ``v0.12.x`` - get the highest v0.12 version
                                - ``v1.x.x`` - get the highest v1 version
    :returns: Descriptor object
    """
    from .descriptor_bundle import AppDescriptor, EngineDescriptor, FrameworkDescriptor
    from .descriptor_config import ConfigDescriptor
    from .descriptor_core import CoreDescriptor

    # if bundle root is not set, fall back on default location
    if bundle_cache_root_override is None:
        bundle_cache_root_override = _get_default_bundle_cache_root()
        filesystem.ensure_folder_exists(bundle_cache_root_override)

    fallback_roots = fallback_roots or []

    # first construct a low level IO descriptor
    io_descriptor = create_io_descriptor(
        sg_connection,
        descriptor_type,
        dict_or_uri,
        bundle_cache_root_override,
        fallback_roots,
        resolve_latest,
        constraint_pattern
    )

    # now create a high level descriptor and bind that with the low level descriptor
    if descriptor_type == Descriptor.APP:
        return AppDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.ENGINE:
        return EngineDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.FRAMEWORK:
        return FrameworkDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.CONFIG:
        return ConfigDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.CORE:
        return CoreDescriptor(io_descriptor)

    else:
        raise TankDescriptorError("Unsupported descriptor type %s" % descriptor_type)


def _get_default_bundle_cache_root():
    """
    Returns the cache location for the default bundle cache.

    :returns: path on disk
    """
    return os.path.join(
        LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE),
        "bundle_cache"
    )


class Descriptor(object):
    """
    A descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Descriptor is subclassed to distinguish different types of payload;
    apps, engines, configs, cores etc. Each payload may have different accessors
    and helper methods.
    """

    (APP, FRAMEWORK, ENGINE, CONFIG, CORE) = range(5)

    def __init__(self, io_descriptor):
        """
        Use the factory method :meth:`create_descriptor` when
        creating new descriptor objects.

        :param io_descriptor: Associated IO descriptor.
        """
        # construct a suitable IO descriptor for this descriptor
        self._io_descriptor = io_descriptor

    def __eq__(self, other):
        # By default, we can assume equality if the path to the data
        # on disk is equivalent.
        if isinstance(other, self.__class__):
            return self.get_path() == other.get_path()
        else:
            return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        """
        Used for debug logging
        """
        class_name = self.__class__.__name__
        return "<%s %r>" % (class_name, self._io_descriptor)

    def __str__(self):
        """
        Used for pretty printing
        """
        return "%s %s" % (self.system_name, self.version)

    ###############################################################################################
    # data accessors

    def get_dict(self):
        """
        Returns the dictionary associated with this descriptor

        :returns: Dictionary that can be used to construct the descriptor
        """
        return self._io_descriptor.get_dict()

    # legacy support for previous method name
    get_location = get_dict

    def get_uri(self):
        """
        Returns the uri associated with this descriptor
        The uri is a string based representation that is equivalent to the
        descriptor dictionary returned by the get_dict() method.

        :returns: Uri string that can be used to construct the descriptor
        """
        return self._io_descriptor.get_uri()

    def copy(self, target_folder):
        """
        Copy the config descriptor into the specified target location

        :param target_folder: Folder to copy the descriptor to
        """
        self._io_descriptor.copy(target_folder)

    @property
    def display_name(self):
        """
        The display name for this item.
        If no display name has been defined, the system name will be returned.
        """
        meta = self._io_descriptor.get_manifest()
        display_name = meta.get("display_name")
        if display_name is None:
            display_name = self.system_name
        return display_name

    def is_dev(self):
        """
        Returns true if this item is intended for development purposes

        :returns: True if this is a developer item
        """
        return self._io_descriptor.is_dev()

    def is_immutable(self):
        """
        Returns true if this descriptor never changes its content.
        This is true for most descriptors as they represent a particular
        version, tag or commit of an item. Examples of non-immutable
        descriptors include path and dev descriptors, where the
        descriptor points at a "live" location on disk where a user
        can make changes at any time.

        :returns: True if this is a developer item
        """
        return self._io_descriptor.is_immutable()

    @property
    def description(self):
        """
        A short description of the item.
        """
        meta = self._io_descriptor.get_manifest()
        desc = meta.get("description")
        if desc is None:
            desc = "No description available." 
        return desc

    @property
    def icon_256(self):
        """
        The path to a 256px square png icon file representing this item
        """
        app_icon = os.path.join(self._io_descriptor.get_path(), "icon_256.png")
        if os.path.exists(app_icon):
            return app_icon
        else:
            # return default
            default_icon = os.path.abspath(os.path.join(
                os.path.dirname(__file__),
                "resources",
                "default_bundle_256px.png"
            ))
            return default_icon

    @property
    def support_url(self):
        """
        A url that points at a support web page associated with this item.
        If not url has been defined, None is returned.
        """
        meta = self._io_descriptor.get_manifest()
        support_url = meta.get("support_url")
        if support_url is None:
            support_url = "https://support.shotgunsoftware.com" 
        return support_url

    @property
    def documentation_url(self):
        """
        The documentation url for this item or None if not defined.
        """
        meta = self._io_descriptor.get_manifest()
        doc_url = meta.get("documentation_url")
        # note - doc_url can be none which is fine.
        return doc_url

    @property
    def deprecation_status(self):
        """
        Information about deprecation status.

        :returns: Returns a tuple (is_deprecated, message) to indicate
                  if this item is deprecated.
        """
        return self._io_descriptor.get_deprecation_status()

    @property
    def system_name(self):
        """
        A short name, suitable for use in configuration files and for folders on disk.
        """
        return self._io_descriptor.get_system_name()
    
    @property
    def version(self):
        """
        The version number string for this item.
        """
        return self._io_descriptor.get_version()
    
    def get_path(self):
        """
        Returns the path to the folder where this item either currently resides
        or would reside in case it existed locally.
        """
        return self._io_descriptor.get_path()

    @property
    def changelog(self):
        """
        Information about the changelog for this item.

        :returns: A tuple (changelog_summary, changelog_url). Values may be None
                  to indicate that no changelog exists.
        """
        return self._io_descriptor.get_changelog()

    def ensure_local(self):
        """
        Helper method. Ensures that the item is locally available.
        """
        return self._io_descriptor.ensure_local()

    def exists_local(self):
        """
        Returns true if this item exists in a local repo.
        """
        return self._io_descriptor.exists_local()

    def download_local(self):
        """
        Retrieves this version to local repo.
        """
        return self._io_descriptor.download_local()

    def find_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        .. note:: Different descriptor types implements this logic differently,
                  but general good practice is to follow the semantic version numbering
                  standard for any versions used in conjunction with toolkit. This ensures
                  that toolkit can track and correctly determine not just the latest version
                  but also apply constraint pattern matching such as looking for the latest
                  version matching the pattern ``v1.x.x``. You can read more about semantic
                  versioning here: http://semver.org/

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: instance derived from :class:`Descriptor`
        """
        # make a copy of the descriptor
        latest = copy.copy(self)
        # find latest I/O descriptor
        latest._io_descriptor = self._io_descriptor.get_latest_version(constraint_pattern)
        return latest

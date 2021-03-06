"""
Copyright [2009-2014] EMBL-European Bioinformatics Institute
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
     http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from cProfile import Profile
import os
import subprocess
import time
from portal.models import Rna
from portal.management.commands.xml_exporters.rna2xml import RnaXmlExporter


class Command(BaseCommand):
    """

    Usage:
    python manage.py xml4dbdumps <options>

    Example:
    python manage.py xml4dbdumps --destination /full/path/to/output/location

    Help:
    python manage.py xml4dbdumps -h
    """

    ########################
    # Command line options #
    ########################

    option_list = BaseCommand.option_list + (
        make_option('-d', '--destination',
            default='',
            dest='destination',
            help='[Required] Full path to the output directory'),

        make_option('--minimum',
            dest='min',
            help='[Required] Minimum RNA id to output'),

        make_option('--maximum',
            dest='max',
            type='int',
            help='[Required] Maximum RNA id to output'),

        make_option('--profile',
            default=False,
            help='[Optional] Show cProfile information for profiling purposes'),
    )
    # shown with -h, --help
    help = ('Export RNAcentral data in xml4dbdump format for EBeye search. '
           'Run `python manage.py export -h` for more information.')

    ######################
    # Django entry point #
    ######################

    def __init__(self, *args, **kwargs):
        """
        Set common variables.
        """
        super(Command, self).__init__(*args, **kwargs)

        self.filename = 'xml4dbdumps__MIN__MAX.xml'
        self.options = {
            'destination': None,
            'min': 0,
            'max': 0,
        }

    def handle(self, *args, **options):
        """
        Main function, called by django.
        """
        def _handle(self, *args, **options):
            """
            Main program. Separated from `handle` to enable Python profiling.
            """
            def set_command_line_options():
                """
                Store command line options in `self.options`.
                """
                cmd_options = ['destination', 'min', 'max']
                for cmd_option in cmd_options:
                    if options[cmd_option]:
                        self.options[cmd_option] = str(options[cmd_option])

            def validate_command_line_options():
                """
                Validate the command line options.
                """
                if not self.options['destination']:
                    raise CommandError('Please specify --destination')
                if not self.options['min']:
                    raise CommandError('Please specify --minimum')
                if not self.options['max']:
                    raise CommandError('Please specify --maximum')
                if not os.path.exists(self.options['destination']):
                    os.makedirs(self.options['destination'])

            set_command_line_options()
            validate_command_line_options()
            self.export_data()

        if options['profile']:
            profiler = Profile()
            profiler.runcall(_handle, self, *args, **options)
            profiler.print_stats()
            profiler.dump_stats('profile.txt')
        else:
            _handle(self, *args, **options)

    ####################
    # Export functions #
    ####################

    def export_data(self):
        """
        Write the data in xml4dbdumps format to the file specified
        in the --destination option.
        """
        def write_xml_header():
            """
            Write out the beginning of the xml file.
            """
            def get_entry_count():
                """
                Get the number of entries to be written out.
                """
                return int(self.options['max']) - int(self.options['min'])

            database = {
                'name': 'RNAcentral',
                'description': ('a database for non-protein coding RNA '
                                'sequences'),
                'release': '1.0',
                'release_date': time.strftime("%d/%m/%Y"),
                'entry_count': get_entry_count(),
            }
            header = """<database>
            <name>{name}</name>
            <description>{description}</description>
            <release>{release}</release>
            <release_date>{release_date}</release_date>
            <entry_count>{entry_count}</entry_count>
            <entries>""".format(**database)
            filehandle.write(header)

        def write_rna_entries():
            """
            Write out RNA entries.
            """
            exporter = RnaXmlExporter()
            for rna in Rna.objects.filter(id__gt=int(self.options['min']), id__lte=int(self.options['max'])).iterator():
                if rna.is_active():
                    filehandle.write(exporter.get_xml_entry(rna))
                    filehandle.flush()

        def write_xml_footer():
            """
            Write out the end of the xml file.
            """
            filehandle.write('</entries></database>')

        def xmllint():
            """
            Run xmllint on the output file and print the resulting report.
            """
            schema_url = 'http://www.ebi.ac.uk/ebisearch/XML4dbDumps.xsd'
            cmd = ('xmllint {filepath} --schema {schema_url} --noout --stream; '
                   'exit 0').format(filepath=filepath, schema_url=schema_url)
            output = subprocess.check_output(cmd, shell=True,
                                             stderr=subprocess.STDOUT)
            if 'validates' not in output:
                print 'ERROR: xmllint validation failed'
                print output

        def gzip_file():
            """
            Gzip output file and keep the original.
            """
            gzipped_filename = '%s.gz' % filepath
            cmd = 'gzip < %s > %s' % (filepath, gzipped_filename)
            status = subprocess.call(cmd, shell=True)
            if status == 0:
                print 'File compressed, new file %s' % gzipped_filename
            else:
                print 'Compressing failed, no file created'

        self.filename = self.filename.replace('MIN', self.options['min']).replace('MAX', self.options['max'])
        filepath = os.path.join(self.options['destination'], self.filename)
        filehandle = open(filepath, 'w')
        write_xml_header()
        write_rna_entries()
        write_xml_footer()
        filehandle.close()
        xmllint()
        gzip_file()

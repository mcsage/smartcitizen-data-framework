''' Implementation of csv export for devices in test '''

from os.path import join, dirname
from scdata.utils import std_out
import flask

def to_csv(self, path = None, forced_overwrite = False):
    """
    Exports devices in test to desired path
    Parameters
    ----------
        path: string
        	None
            The path (directory) to export the csv(s) into. If None, exports to test_path/processed/
        forced_overwrite: boolean
        	False
            To overwrite existing files
    Returns
    -------
        True if export successul
    """	
    export_ok = True

    if path is None: epath = join(self.path, 'processed')
    else: epath = path

    # Export to csv
    for device in self.devices.keys():
        export_ok &= self.devices[device].export(epath, forced_overwrite = forced_overwrite)

    if export_ok: std_out(f'Test {self.full_name} exported successfully', 'SUCCESS')
    else: std_out(f'Test {self.full_name} not exported successfully', 'ERROR')

    return export_ok

def desc_to_html(self, title = 'Test description', path = None, show_logo = True):
    '''
    Generates an html description for the test
    Inspired by the code of rbardaji in: https://github.com/rbardaji/mooda
    Parameters
    ----------
        title: String
            None
            Document title
        path: String
            None
            Directory to export it to. If None, writes it to default test folder
        show_logo: bool
            True
            Show logo or not
    Returns
    ----------
        filename: String
            Path to file
    '''

    # Find the path to the html templates directory
    template_folder = join(dirname(__file__), 'templates')

    if path is None: path = self.path
    filename = join(path, 'test_description.html')
    
    app = flask.Flask('test descriptor', template_folder = template_folder)

    with app.app_context():
        rendered = flask.render_template(
            'descriptor.html',
            title = title,
            descriptor = self.descriptor,
            show_logo = show_logo
        )

    with open(filename, 'w') as handle:
        handle.write(rendered)
    
    return filename
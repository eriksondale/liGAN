from __future__ import print_function, division
import matplotlib
matplotlib.use('Agg')
import sys
import os
import re
import glob
import argparse
import parse
import pandas as pd
pd.set_option('display.max_columns', 100)
pd.set_option('display.max_colwidth', 100)
pd.set_option('display.width', 200)
from pandas.api.types import is_numeric_dtype
import numpy as np
np.random.seed(0)
import matplotlib.pyplot as plt
import seaborn as sns
import random
sns.set_style('whitegrid')
sns.set_context('notebook')
sns.set_palette('Set1')

import models


def plot_lines(plot_file, df, x, y, hue, n_cols=None, height=4, width=4, outlier_z=None):
    df = df.reset_index()
    xlim = (df[x].min(), df[x].max())
    if hue:
        df = df.set_index([hue, x])
    elif df.index.name != x:
        df = df.set_index(x)
    if n_cols is None:
        n_cols = len(y)
    n_axes = len(y)
    assert n_axes > 0
    n_rows = (n_axes + n_cols-1)//n_cols
    n_cols = min(n_axes, n_cols)
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(width*n_cols, height*n_rows),
                             sharex=len(x) == 1,
                             sharey=len(y) == 1,
                             squeeze=False)
    iter_axes = iter(axes.flatten())
    extra = []
    for i, y_ in enumerate(y):

        if outlier_z is not None:
            df[y_] = replace_outliers(df[y_], np.nan, z=outlier_z)

        ax = next(iter_axes)
        ax.set_xlabel(x)
        ax.set_ylabel(y_)
        if y_.endswith('log_loss'):
            ax.hlines(-np.log(0.5), *xlim, linestyle=':', linewidth=1.0)
        
        ax.hlines(0, *xlim, linestyle='-', linewidth=1.0)

        if hue:
            alpha = 0.5/df.index.get_level_values(hue).nunique()
            for j, _ in df.groupby(level=0):
                mean = df.loc[j][y_].groupby(level=0).mean()
                sem = df.loc[j][y_].groupby(level=0).sem()
                ax.fill_between(mean.index, mean-sem, mean+sem, alpha=alpha)
            for j, _ in df.groupby(level=0):
                mean = df.loc[j][y_].groupby(level=0).mean()
                ax.plot(mean.index, mean, label=j)
        else:
            mean = df[y_].groupby(level=0).mean()
            sem = df[y_].groupby(level=0).sem()
            ax.fill_between(mean.index, mean-sem, mean+sem, alpha=0.5)
            ax.plot(mean.index, mean)
        handles, labels = ax.get_legend_handles_labels()
        ax.set_xlim(xlim)

    if hue: # add legend
        lgd = fig.legend(handles, labels, loc='upper left', bbox_to_anchor=(1, 1), ncol=1, frameon=False, borderpad=0.5)
        lgd.set_title(hue, prop=dict(size='small'))
        extra.append(lgd)
    for ax in iter_axes:
        ax.axis('off')
    fig.tight_layout()
    fig.savefig(plot_file, bbox_extra_artists=extra, bbox_inches='tight')
    plt.close(fig)


def replace_outliers(x, value, z=3):
    x_mean = np.mean(x)
    x_std = np.std(x)
    x_max = x_mean + z*x_std
    x_min = x_mean - z*x_std
    return np.where(x > x_max, value, np.where(x < x_min, value, x))


def plot_strips(plot_file, df, x, y, hue, n_cols=None, height=3, width=3, outlier_z=None):
    df = df.reset_index()
    if n_cols is None:
        n_cols = len(x) - bool(hue)
    n_axes = len(x)*len(y)
    assert n_axes > 0
    n_rows = (n_axes + n_cols-1)//n_cols
    n_cols = min(n_axes, n_cols)
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(width*n_cols, height*n_rows),
                             sharex=len(x) == 1,
                             sharey=len(y) == 1,
                             squeeze=False)
    iter_axes = iter(axes.flatten())
    extra = []
    violin = False
    for y_ in y:

        if outlier_z is not None:
            df[y_] = replace_outliers(df[y_], np.nan, z=outlier_z)

        for x_ in x:
            ax = next(iter_axes)
            sns.pointplot(data=df, x=x_, y=y_, hue=hue, dodge=0.525, markers='', ax=ax)
            ylim = ax.get_ylim()
            alpha = 0.25
            if violin:
                sns.violinplot(data=df, x=x_, y=y_, hue=hue, dodge=True, inner=None, saturation=1.0, linewidth=0.0, ax=ax)
                for c in ax.collections:
                    if isinstance(c, matplotlib.collections.PolyCollection):
                        c.set_alpha(alpha)
            else:
                sns.stripplot(data=df, x=x_, y=y_, hue=hue, dodge=0.525, jitter=0.2, size=5, alpha=alpha, ax=ax)
            handles, labels = ax.get_legend_handles_labels()
            handles = handles[len(handles)//2:]
            labels = labels[len(labels)//2:]
            ax.set_ylim(ylim)
            if hue:
                ax.legend_.remove()

    if hue: # add legend
        lgd = fig.legend(handles, labels, loc='upper left', bbox_to_anchor=(1, 1), ncol=1, frameon=False, borderpad=0.5)
        lgd.set_title(hue, prop=dict(size='small'))
        extra.append(lgd)
    for ax in iter_axes:
        ax.axis('off')
    fig.tight_layout()
    fig.savefig(plot_file, bbox_extra_artists=extra, bbox_inches='tight')
    plt.close(fig)


def read_training_output_files(model_dirs, data_name, seeds, folds, iteration, check):
    all_model_dfs = []
    for model_dir in model_dirs:
        model_dfs = []
        model_name = model_dir.rstrip('/\\')
        model_prefix = os.path.join(model_dir, model_name)
        model_errors = dict()
        for seed in seeds:
            for fold in folds:
                try:
                    file_ = '{}.{}.{}.{}.training_output'.format(model_prefix, data_name, seed, fold)
                    file_df = pd.read_csv(file_, sep=' ')
                    file_df['model_name'] = model_name
                    #file_df['data_name'] = data_name #TODO allow multiple data sets
                    file_df['seed'] = seed
                    file_df['fold'] = fold
                    file_df['iteration'] = file_df['iteration'].astype(int)
                    if 'base_lr' in file_df:
                        del file_df['base_lr']
                    max_iter = file_df['iteration'].max()
                    assert iteration in file_df['iteration'].unique(), \
                        'No training output for iteration {} ({})'.format(iteration, max_iter)
                    model_dfs.append(file_df)
                except (IOError, pd.io.common.EmptyDataError, AssertionError, KeyError) as e:
                    model_errors[file_] = e
        if not check or not model_errors:
            all_model_dfs.extend(model_dfs)
        else:
            for f, e in model_errors.items():
                print('{}: {}'.format(f, e))
    return pd.concat(all_model_dfs)


def add_data_from_name_parse(df, index, prefix, name_format, name):
    name_parse = parse.parse(name_format, name)
    if name_parse is None:
        raise Exception('could not parse {} with format {}'.format(repr(name), repr(name_format)))
    name_fields = []
    for field in sorted(name_parse.named, key=name_parse.spans.get):
        value = name_parse.named[field]
        if prefix:
            field = '{}_{}'.format(prefix, field)
        df.loc[index, field] = value
        name_fields.append(field)
    return name_fields


def fix_name(name, char, idx):
    '''
    Split name into fields by underscore, append char to
    fields at each index in idx, then rejoin by underscore.
    '''
    fields = name.split('_')
    for i in idx:
        fields[i] += char
    return '_'.join(fields)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--dir_pattern', default=[], action='append', required=True)
    parser.add_argument('-d', '--data_name', default='lowrmsd')
    parser.add_argument('-s', '--seeds', default='0')
    parser.add_argument('-f', '--folds', default='0,1,2')
    parser.add_argument('-i', '--iteration', default=20000, type=int)
    parser.add_argument('-o', '--out_prefix', default='')
    parser.add_argument('-r', '--rename_col', default=[], action='append')
    parser.add_argument('-x', '--x', default=[], action='append')
    parser.add_argument('-y', '--y', default=[], action='append')
    parser.add_argument('--outlier_z', default=None, type=float)
    parser.add_argument('--hue', default=None)
    parser.add_argument('--n_cols', default=4, type=int)
    parser.add_argument('--masked', default=False, action='store_true')
    parser.add_argument('--plot_lines', default=False, action='store_true')
    parser.add_argument('--plot_strips', default=False, action='store_true')
    parser.add_argument('--plot_ext', default='png')
    parser.add_argument('--aggregate', default=False, action='store_true')
    parser.add_argument('--test_data')
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    # read training output files from found model directories
    model_dirs = sorted(d for p in args.dir_pattern for d in glob.glob(p) if os.path.isdir(d))
    seeds = args.seeds.split(',')
    folds = args.folds.split(',')
    df = read_training_output_files(model_dirs, args.data_name, seeds, folds, args.iteration, True)

    if args.test_data is not None:
        df = df[df['test_data'] == args.test_data]

    # aggregate output values for each model across seeds and folds
    index_cols = ['model_name', 'iteration']
    if args.aggregate:
        f = {col: pd.Series.nunique if col in {'seed', 'fold'} else np.mean \
                for col in df if col not in index_cols}
        agg_df = df.groupby(index_cols).agg(f)
        assert np.all(agg_df['seed'] == len(seeds))
        assert np.all(agg_df['fold'] == len(folds))
    else:
        agg_df = df.set_index(index_cols)

    # add columns from parsing model name fields
    for model_name, model_df in agg_df.groupby(level=0):

        # try to parse it as a GAN
        m = re.match(r'^(.+_)?(.+e(\d+)_.+)_(d(\d+)_.+)$', model_name)
        solver_name = fix_name(m.group(1), ' ', [3])
        name_fields = add_data_from_name_parse(agg_df, model_name, '', models.SOLVER_NAME_FORMAT, solver_name)

        gen_v = tuple(int(c) for c in m.group(3))
        if gen_v == (1, 4):
            gen_model_name = fix_name(m.group(2), ' ', [-1, -2])
        elif gen_v == (1, 3):            
            gen_model_name = fix_name(m.group(2), ' ', [-1, -5])
        else:
            gen_model_name = m.group(2)
        agg_df.loc[model_name, 'gen_model_version'] = str(gen_v)
        name_fields.append('gen_model_version')
        name_fields += add_data_from_name_parse(agg_df, model_name, 'gen', models.GEN_NAME_FORMATS[gen_v], gen_model_name)

        disc_v = tuple(int(c) for c in m.group(5))
        disc_model_name = m.group(4)
        agg_df.loc[model_name, 'disc_model_version'] = str(disc_v)
        name_fields.append('disc_model_version')
        name_fields += add_data_from_name_parse(agg_df, model_name, 'disc', models.DISC_NAME_FORMATS[disc_v], disc_model_name)

    # fill in default values so that different model versions may be compared
    if 'resolution' in agg_df:
        agg_df['resolution'] = agg_df['resolution'].fillna(0.5)

    if 'conv_per_level' in agg_df:
        agg_df = agg_df[agg_df['conv_per_level'] > 0]

    if 'width_factor' in agg_df:
        agg_df['width_factor'] = agg_df['width_factor'].fillna(1)
        agg_df = agg_df[agg_df['width_factor'] < 3]

    if 'n_latent' in agg_df:
        agg_df['n_latent'] = agg_df['n_latent'].fillna(0)

    if 'loss_types' in agg_df:
        agg_df['loss_types'] = agg_df['loss_types'].fillna('e')

    if args.masked: # treat rmsd_loss as masked loss; adjust for resolution

        rmsd_losses = [l for l in agg_df if 'rmsd_loss' in l]
        for rmsd_loss in rmsd_losses:

            no_rmsd = agg_df[rmsd_loss].isnull()
            agg_df.loc[no_rmsd, rmsd_loss] = agg_df[no_rmsd][rmsd_loss.replace('rmsd_loss', 'loss')]
            agg_df[rmsd_loss] *= agg_df['resolution']**3

    # rename columns if necessary
    agg_df.reset_index(inplace=True)
    col_name_map = {col: col for col in agg_df}
    col_name_map.update(dict(r.split(':') for r in args.rename_col))
    agg_df.rename(columns=col_name_map, inplace=True)
    name_fields = [col_name_map[n] for n in name_fields]

    # by default, don't make separate plots for the hue variable or variables with 1 unique value
    if not args.x:
        args.x = [n for n in name_fields if n != args.hue and agg_df[n].nunique() > 1]

    if args.plot_lines: # plot training progress
        line_plot_file = '{}_lines.{}'.format(args.out_prefix, args.plot_ext)
        plot_lines(line_plot_file, agg_df, x=col_name_map['iteration'], y=args.y, hue=args.hue,
                   n_cols=args.n_cols, outlier_z=args.outlier_z)

    final_df = agg_df.set_index(col_name_map['iteration']).loc[args.iteration]
 
    print('\nfinal data')
    print(final_df)
    
    if args.plot_strips: # plot final loss distributions
        strip_plot_file = '{}_strips.{}'.format(args.out_prefix, args.plot_ext)
        plot_strips(strip_plot_file, final_df, x=args.x, y=args.y, hue=args.hue,
                    n_cols=args.n_cols, outlier_z=args.outlier_z)

    # display names of best models
    print('\nbest models')
    for y in args.y:
        print(final_df.sort_values(y).loc[:, (col_name_map['model_name'], y)].head(5))


if __name__ == '__main__':
    main(sys.argv[1:])
